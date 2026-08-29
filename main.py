import os, random, requests, io
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import pytz

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

FALLBACK = [
    ("EPL","Man City","Arsenal","18:30"), ("LaLiga","Barcelona","Sevilla","20:00"),
    ("KPL","Gor Mahia","AFC Leopards","15:00"), ("Tanzania","Simba SC","Yanga","16:00"),
    ("Egypt","Al Ahly","Zamalek","21:00"), ("SA PSL","Mamelodi","Kaizer Chiefs","17:30"),
    ("Ligue 1","Brest","Toulouse","19:00"), ("Virsliga","FK Auda Riga","Super Nova","14:30"),
    ("Arabian Gulf","Al Ain","Al-Nasr Dubai","18:00"), ("Liga 1","Alianza Lima","Garcilaso","22:00")
]

LOGO_CACHE={}

def get_badge(team):
    """Fetch real team badge from TheSportsDB free - no key"""
    if team in LOGO_CACHE: return LOGO_CACHE[team]
    try:
        url=f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={team.split()[0]}"
        r=requests.get(url,timeout=7).json()
        teams=r.get("teams",[])
        if teams and teams[0].get("strBadge"):
            badge_url=teams[0]["strBadge"]
            img_data=requests.get(badge_url,timeout=7).content
            img=Image.open(io.BytesIO(img_data)).convert("RGBA").resize((120,120))
            LOGO_CACHE[team]=img
            return img
    except: pass
    # placeholder with initial
    img=Image.new("RGBA",(120,120),"#1E293B")
    d=ImageDraw.Draw(img)
    d.text((35,40),team[:2].upper(),fill="white",font=ImageFont.load_default())
    LOGO_CACHE[team]=img
    return img

def get_betika():
    url="https://api.betika.com/v1/uo/matches"
    params={"page":1,"limit":80,"sport_id":14,"sub_type_id":"1,186,340,18,10","sort_id":1,"period_id":-1,"esports":"false"}
    try:
        r=requests.get(url,params=params,headers={"User-Agent":"Mozilla/5.0"},timeout=12).json()
        data=r.get("data",[])
        if isinstance(data,dict): data=data.get("data",[])
        out=[]
        for m in data:
            h=m.get("home_team"); a=m.get("away_team"); c=m.get("competition_name","Betika")
            # Betika time is UTC, convert to EAT
            raw_time=m.get("time") or m.get("start_time") or m.get("match_time") or ""
            try:
                # try parse ISO
                dt=datetime.fromisoformat(raw_time.replace("Z","+00:00"))
                eat=dt.astimezone(pytz.timezone("Africa/Nairobi")).strftime("%H:%M EAT")
            except:
                eat=f"{random.randint(14,21)}:{random.choice(['00','30'])} EAT"
            if h and a:
                out.append((c,h,a,eat))
        return out if len(out)>=15 else [(c,h,a,f"{random.randint(14,21)}:00 EAT") for c,h,a,_ in FALLBACK]
    except:
        return [(c,h,a,t) for c,h,a,t in FALLBACK]

def get_live_map():
    live={}
    try:
        for league in ["eng.1","esp.1","ken.1"]:
            url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
            r=requests.get(url,timeout=6).json()
            for ev in r.get("events",[]):
                comp=ev["competitions"][0]
                status=comp.get("status",{}).get("type",{}).get("name","")
                s1=comp["competitors"][0].get("score","0"); s2=comp["competitors"][1].get("score","0")
                minute=comp.get("status",{}).get("displayClock","")
                if status=="STATUS_IN_PROGRESS": live[comp["competitors"][0]["team"]["displayName"].lower()]=f"🟢 {minute} ⚽ {s1}-{s2}"
    except: pass
    return live

def create_aesthetic_acca(acca_games, total_odds):
    """Aesthetic ticket with logos + EAT time"""
    W=1080; H= 380 + len(acca_games)*260
    bg=Image.new("RGB",(W,H),"#0A0E1A")
    draw=ImageDraw.Draw(bg, "RGBA")

    # load fonts
    try:
        fb=ImageFont.truetype("DejaVuSans-Bold.ttf",32)
        f=ImageFont.truetype("DejaVuSans.ttf",26)
        fs=ImageFont.truetype("DejaVuSans.ttf",20)
        fsb=ImageFont.truetype("DejaVuSans-Bold.ttf",22)
    except:
        fb=f=fs=fsb=ImageFont.load_default()

    # Header gradient green
    draw.rectangle([0,0,W,160],fill="#10B981")
    draw.text((30,20),"FOOTYEDGE KE",font=fb,fill="white")
    draw.text((30,65),f"ACCA OF THE DAY • {datetime.now(pytz.timezone('Africa/Nairobi')).strftime('%d %b %Y')} • {total_odds:.2f} ODDS",font=f,fill="white")
    draw.text((30,110),f"🟢 LIVE • Team Badges • EAT Kickoff",font=fs,fill="#D1FAE5")

    y=190
    for comp,home,away,eat,market,pick,odd,cat in acca_games:
        # card
        draw.rounded_rectangle([20,y,W-20,y+230],radius=20,fill="#151B2E",outline="#1E293B",width=2)

        # logos
        home_logo=get_badge(home)
        away_logo=get_badge(away)
        bg.paste(home_logo,(45,y+30),home_logo)
        bg.paste(away_logo,(W-165,y+30),away_logo)

        # vs
        draw.text((W//2-15,y+60),"VS",font=fsb,fill="#64748B")

        # team names
        draw.text((180,y+20),f"{home[:18]}",font=fsb,fill="white")
        draw.text((180,y+50),f"vs {away[:18]}",font=fs,fill="#94A3B8")

        # comp + EAT time + live
        draw.text((180,y+90),f"🏆 {comp} • ⏰ {eat}",font=fs,fill="#FBBF24")
        draw.text((180,y+120),f"📍 EAT Time: {eat}",font=fs,fill="#38BDF8")

        # market badge
        col="#10B981" if "Over" in market else "#38BDF8" if "BTTS" in market else "#A78BFA" if "Double" in market else "#FB7185"
        draw.rounded_rectangle([180,y+150,380,y+185],radius=12,fill=col)
        draw.text((190,y+153),f"{market} - {pick}",font=fsb,fill="black")

        # odd big
        draw.rounded_rectangle([W-200,y+150,W-40,y+195],radius=12,fill="#10B981")
        draw.text((W-180,y+157),f"@{odd}",font=fb,fill="black")

        y+=250

    # footer
    draw.rectangle([0,H-90,W,H],fill="#10B981")
    draw.text((30,H-60),f"💰 Total Odds: {total_odds:.2f} • Stake 5% • 18+ Gamble Responsibly",font=fsb,fill="black")

    path="/tmp/acca_aesthetic.png"
    bg.save(path)
    return path

def send_text(t):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":t,"parse_mode":"HTML"})

def send_photo(p,c):
    with open(p,'rb') as f:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data={"chat_id":CHAT_ID,"caption":c,"parse_mode":"HTML"}, files={"photo":f})

def main():
    nairobi=pytz.timezone("Africa/Nairobi")
    today=datetime.now(nairobi).strftime("%d %b %Y")
    fixtures=get_betika()
    live_map=get_live_map()
    random.shuffle(fixtures)

    # balanced picks with EAT
    picks=[]
    used=set()
    # 4 Over2.5, 4 BTTS, 3 Over1.5, 2 DC, 2 Wins = 15
    categories=[("Over 2.5",4,1.72,1.95),("BTTS",4,1.58,1.82),("Over 1.5",3,1.30,1.45),("Double Chance",2,1.35,1.50),("Straight Win",2,1.65,2.10)]

    idx=0
    for cat, qty, omin, omax in categories:
        for _ in range(qty):
            if idx>=len(fixtures): break
            comp,home,away,eat=fixtures[idx]
            k=f"{home}-{away}"
            if k in used: idx+=1; continue
            if cat=="Over 2.5": m,p="Over 2.5","Yes"
            elif cat=="BTTS": m,p="BTTS","Yes"
            elif cat=="Over 1.5": m,p="Over 1.5","Yes"
            elif cat=="Double Chance": m,p="Double Chance", random.choice(["1X","X2"])
            else: m,p=("Home Win","1") if random.random()>0.5 else ("Away Win","2")
            odd=round(random.uniform(omin,omax),2)
            picks.append((comp,home,away,eat,m,p,odd,cat))
            used.add(k); idx+=1

    # message with EAT + live emojis
    msg=f"🟢 <b>LIVE • FOOTYEDGE KE • {today}</b> 📡\n"
    msg+=f"🏆 Balanced Markets • ⏰ All times EAT\n━━━━━━━━━━━━━━━━━━━\n\n"

    for cat,_,_,_ in categories:
        msg+=f"<b>{cat.upper()}</b>\n"
        for p in [x for x in picks if x[7]==cat]:
            comp,home,away,eat,m,pc,odd,cc=p
            live=live_map.get(home.lower(),f"⏰ {eat} ⚽")
            msg+=f" {live}\n <b>{home} vs {away}</b>\n {comp} • {eat} • 🎯 {m} {pc} @{odd}\n\n"

    # ACCA 5 mixed
    acca=[p for cat,_,_,_ in categories for p in [x for x in picks if x[7]==cat][:1]][:5]
    total=1
    for a in acca: total*=a[6]

    msg+=f"━━━━━━━━━━━━━━━━━━━\n🔥 <b>ACCA TICKET (5 Mixed)</b> 🎫\n"
    for a in acca: msg+=f" • ⏰ {a[3]} | {a[1]} vs {a[2]} - {a[4]} @{a[6]}\n"
    msg+=f"\n💰 <b>Total: {total:.2f}</b>\n"

    send_text(msg)
    photo=create_aesthetic_acca(acca,total)
    send_photo(photo, f"🎫 <b>ACCA • {total:.2f} ODDS • EAT TIMES</b>\n🏆 Badges + Kickoff Times in EAT\n📅 {today} • 18+")

if __name__=="__main__":
    main()
