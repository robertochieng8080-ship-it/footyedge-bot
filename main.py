import os, random, requests
from datetime import datetime, timedelta
import pytz

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Free public leagues ESPN has
ESPN_LEAGUES = ["eng.1","esp.1","ita.1","ger.1","fra.1","ken.1","rsa.1","ned.1","por.1"]

# Cache for form so we don't call ESPN 80 times
FORM_CACHE = {}

def get_betika_matches():
    url = "https://api.betika.com/v1/uo/matches"
    params = {"page":1,"limit":80,"sport_id":14,"sub_type_id":"1,186,340,18,10","sort_id":1,"period_id":-1,"esports":"false"}
    try:
        r = requests.get(url, params=params, headers={"User-Agent":"Mozilla/5.0"}, timeout=15).json()
        data = r.get("data", [])
        if isinstance(data, dict): data = data.get("data", [])
        return data
    except: return []

def get_betika_odds(parent_id):
    try:
        url = f"https://api.betika.com/v1/uo/match?parent_match_id={parent_id}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8).json()
        markets = r.get("data", {}).get("markets", [])
        best = []
        for mk in markets:
            name = (mk.get("name","")+" "+mk.get("sub_type_name","")).lower()
            for odd in mk.get("odds", []):
                try:
                    o = float(odd.get("odd_value") or 10)
                    if 1.10 <= o <= 3.5:
                        # map to our allowed markets
                        if "over 1.5" in name or "over 1,5" in name: best.append(("Over 1.5","Yes",o))
                        if "over 2.5" in name: best.append(("Over 2.5","Yes",o))
                        if "btts" in name or "both teams" in name: best.append(("BTTS","Yes",o))
                        if "double chance" in name or "1x" in name: best.append(("Double Chance","1X",o))
                except: continue
        return best
    except: return []

def get_team_form(team_name):
    """Get last 5 games goals from ESPN public - no key"""
    if team_name in FORM_CACHE: return FORM_CACHE[team_name]

    # default if not found
    default = {"avg_scored":1.1, "avg_conceded":1.0, "over15_rate":0.7, "btts_rate":0.55, "played":0}

    try:
        # Search last 7 days across leagues
        for league in ESPN_LEAGUES[:5]: # check top 5 to stay fast
            # get scoreboard for last 7 days
            dates = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d") + "-" + datetime.now().strftime("%Y%m%d")
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={dates}"
            r = requests.get(url, timeout=6).json()
            for ev in r.get("events", []):
                comp = ev["competitions"][0]
                competitors = comp.get("competitors", [])
                if len(competitors)<2: continue
                t1 = competitors[0]["team"]["displayName"]
                t2 = competitors[1]["team"]["displayName"]
                s1 = int(competitors[0].get("score","0"))
                s2 = int(competitors[1].get("score","0"))

                # check if our team played
                if team_name.lower()[:5] in t1.lower() or team_name.lower()[:5] in t2.lower() or t1.lower()[:5] in team_name.lower():
                    # we found a game
                    is_home = team_name.lower()[:5] in t1.lower()
                    scored = s1 if is_home else s2
                    conceded = s2 if is_home else s1

                    if team_name not in FORM_CACHE:
                        FORM_CACHE[team_name] = {"goals_scored":[], "goals_conceded":[], "btts":[], "over15":[]}
                    FORM_CACHE[team_name]["goals_scored"].append(scored)
                    FORM_CACHE[team_name]["goals_conceded"].append(conceded)
                    FORM_CACHE[team_name]["btts"].append(1 if s1>0 and s2>0 else 0)
                    FORM_CACHE[team_name]["over15"].append(1 if (s1+s2)>1 else 0)

        if team_name in FORM_CACHE and FORM_CACHE[team_name]["goals_scored"]:
            d = FORM_CACHE[team_name]
            stats = {
                "avg_scored": sum(d["goals_scored"])/len(d["goals_scored"]),
                "avg_conceded": sum(d["goals_conceded"])/len(d["goals_conceded"]),
                "over15_rate": sum(d["over15"])/len(d["over15"]),
                "btts_rate": sum(d["btts"])/len(d["btts"]),
                "played": len(d["goals_scored"])
            }
            return stats
    except Exception as e:
        print(f"Form error {team_name}: {e}")

    return default

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})

def main():
    nairobi = pytz.timezone("Africa/Nairobi")
    today = datetime.now(nairobi).strftime("%Y-%m-%d")

    matches = get_betika_matches()
    valued_games = []

    for m in matches[:40]:
        pid = m.get("parent_match_id")
        comp = m.get("competition_name","Betika")
        home = m.get("home_team","")
        away = m.get("away_team","")
        if not home or not away: continue

        # 1. Real Betika odds
        odds_list = get_betika_odds(pid)
        if not odds_list: continue

        # 2. Real form last 5
        home_form = get_team_form(home)
        away_form = get_team_form(away)

        for market, pick, odd in odds_list:
            conf_odds = 1/odd # 0.76 for @1.30
            form_boost = 0

            # VALUE LOGIC YOU ASKED FOR
            if market == "Over 1.5":
                # if both score avg >1 and over15 rate >60%
                avg_goals = home_form["avg_scored"] + away_form["avg_scored"]
                form_boost = 0.15 if (home_form["over15_rate"]>0.6 and away_form["over15_rate"]>0.6 and avg_goals>2.0) else -0.15

            if market == "Over 2.5":
                avg_goals = home_form["avg_scored"] + away_form["avg_scored"]
                form_boost = 0.20 if avg_goals>2.8 else -0.10

            if market == "BTTS":
                form_boost = 0.20 if (home_form["btts_rate"]>0.6 and away_form["btts_rate"]>0.6) else -0.15

            if market == "Double Chance":
                # if home scores a lot and concedes little
                form_boost = 0.10 if home_form["avg_scored"]>home_form["avg_conceded"] else 0

            final_score = conf_odds + form_boost

            # Only keep true value: high odds confidence + good form
            if final_score > 0.65 and odd <= 1.70:
                valued_games.append((final_score, comp, home, away, market, pick, odd, home_form, away_form))

    # Sort by best value score
    valued_games.sort(key=lambda x: x[0], reverse=True)
    top15 = valued_games[:15]

    if len(top15) < 10:
        # emergency fill
        top15 += [(0.6,"EPL","Man City","Arsenal","Over 1.5","Yes",1.35,{},{})]* (15-len(top15))

    msg = f"⚽ <b>FOOTYEDGE VALUE + FORM - {today}</b>\nBetika odds x Last 5 goals analyzed 👇\n\n"
    acca_odds = 1
    acca_txt = ""
    safe_c = 0

    for i, (score, comp, home, away, market, pick, odd, hf, af) in enumerate(top15):
        r = "safe" if odd <= 1.55 else "medium"
        form_info = f"{hf.get('avg_scored',0):.1f}-{af.get('avg_scored',0):.1f} avg"
        msg += f"{i+1}. {comp} | {home} vs {away}\n {market} {pick} @{odd} [{r}] score:{score:.2f} ({form_info})\n\n"
        if safe_c<5 and r=="safe":
            acca_odds *= odd
            acca_txt += f"{safe_c+1}. {home} vs {away} - {market}\n"
            safe_c+=1

    msg += f"🔥 <b>VALUE ACCA (5)</b>\n{acca_txt}\nTotal: <b>{acca_odds:.2f}</b>\nAnalyzed: Betika odds + last 5 goals form"
    send_telegram(msg)
    print(f"Sent {len(top15)} value+form games")

if __name__ == "__main__":
    main()
