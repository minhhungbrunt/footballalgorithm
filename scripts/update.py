#!/usr/bin/env python3
"""
Football Edge data updater.

Source: FotMob public web endpoints.
Designed for GitHub Actions. It never replaces a good fixture file with
an empty response, and it keeps all fixtures returned for the selected
competitions instead of truncating to the first match.
"""
import json, os, sys, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE="https://www.fotmob.com/api/data"
LEAGUES={
    "Premier League":47,
    "LaLiga":87,
    "Bundesliga":54,
    "Serie A":55,
    "Ligue 1":53,
    "Eredivisie":57,
    "Primeira Liga":61,
}
# Major competitions are included on days where they have fixtures.
EXTRA_NAMES=("UEFA Champions League","UEFA Europa League","UEFA Conference League",
             "EFL Cup","FA Cup","Copa del Rey","DFB Pokal","Coppa Italia","Coupe de France")

def fetch(url):
    req=Request(url,headers={
        "User-Agent":"Mozilla/5.0 (compatible; FootballEdge/1.0)",
        "Accept":"application/json,text/plain,*/*",
        "Referer":"https://www.fotmob.com/",
    })
    with urlopen(req,timeout=30) as r:
        return json.load(r)

def first(d,*keys):
    for k in keys:
        v=d.get(k)
        if v not in (None,"",0): return v
    return None

def normalize_match(m,league_name):
    h=m.get("home") or {}
    a=m.get("away") or {}
    status=m.get("status") or {}
    return {
        "id":str(m.get("id") or m.get("matchId") or ""),
        "home":first(h,"name","longName") or "Home",
        "away":first(a,"name","longName") or "Away",
        "competition":league_name,
        "time":first(status,"utcTime","time","startTime") or m.get("time") or "",
        "status":"finished" if status.get("finished") else ("live" if status.get("started") else "upcoming"),
        "homePos":first(h,"tablePosition","position","rank"),
        "awayPos":first(a,"tablePosition","position","rank"),
    }

def score_league(n):
    order=["Premier League","LaLiga","Bundesliga","Serie A","Ligue 1","Eredivisie","Primeira Liga"]
    return 100-order.index(n)*3 if n in order else 50

def get_matches():
    eastern=datetime.now(ZoneInfo("America/New_York"))
    date=eastern.strftime("%Y%m%d")
    raw=fetch(f"{BASE}/matches?date={date}")
    matches=[]
    for league in raw.get("leagues",[]):
        name=first(league,"name","leagueName") or "Unknown"
        # Keep top 7; also keep major cup/European competition fixtures.
        if name not in LEAGUES and not any(x.lower() in name.lower() for x in EXTRA_NAMES):
            continue
        for m in league.get("matches",[]) or []:
            nm=normalize_match(m,name)
            if nm["id"] and nm["home"]!="Home":
                matches.append(nm)
    # Deduplicate without dropping matches.
    seen=set(); out=[]
    for m in matches:
        if m["id"] in seen: continue
        seen.add(m["id"]); out.append(m)
    out.sort(key=lambda m:(-score_league(m["competition"]),m["time"] or ""))
    return date,out

def main():
    os.makedirs("data",exist_ok=True)
    path="data/fixtures.json"
    try:
        date,matches=get_matches()
        if not matches:
            raise RuntimeError("FotMob returned zero accepted fixtures; refusing to overwrite existing data.")
        payload={
            "updated":datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET"),
            "date":date,
            "source":"FotMob",
            "fixtureCount":len(matches),
            "leagues":list(LEAGUES.keys()),
            "matches":matches,
        }
        with open(path,"w",encoding="utf-8") as f: json.dump(payload,f,ensure_ascii=False,indent=2)
        print(f"Updated {len(matches)} fixtures for {date}")
    except Exception as e:
        print("UPDATE FAILED:",repr(e))
        if os.path.exists(path):
            print("Keeping existing fixture file.")
            return
        raise

if __name__=="__main__":
    main()
