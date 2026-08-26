import datetime as dt
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("America/New_York")
ROOT = "https://www.fotmob.com"
HEAD = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.fotmob.com/",
    "Origin": "https://www.fotmob.com",
    "Cache-Control": "no-cache",
}
CACHE = {}
TEAM_CACHE = {}
DETAIL_CACHE = {}
LEAGUE_CACHE = {}

# Major competitions. Premier League is deliberately resolved with its country/ccode.
SUPPORTED = {
    "Premier League", "Championship", "League One", "League Two", "EFL Cup", "FA Cup",
    "LaLiga", "LaLiga 2", "Copa del Rey", "Bundesliga", "2. Bundesliga", "DFB Pokal",
    "Serie A", "Serie B", "Coppa Italia", "Ligue 1", "Ligue 2", "Coupe de France",
    "Eredivisie", "KNVB Beker", "Primeira Liga", "Taça de Portugal",
    "Scottish Premiership", "Scottish Cup", "Belgian Pro League", "Belgian Cup",
    "Turkish Super Lig", "Turkish Cup", "UEFA Champions League", "Champions League",
    "UEFA Europa League", "Europa League", "UEFA Conference League", "Conference League",
    "UEFA Champions League Qualification", "Champions League Qualification",
    "UEFA Europa League Qualification", "Europa League Qualification",
    "UEFA Conference League Qualification", "Conference League Qualification",
    "MLS", "Liga MX", "Saudi Pro League", "Brasileirão", "Copa Libertadores", "Copa Sudamericana",
    "J1 League", "K League 1", "A-League", "Liga Argentina", "Primera Division",
    "U.S. Open Cup", "CONCACAF Champions Cup", "Copa do Brasil", "Colombian Primera A",
}

# Broad structural priors. These are not betting odds.
STRENGTH = {
    "Premier League": 1885, "UEFA Champions League": 1890, "Champions League": 1890,
    "LaLiga": 1870, "Bundesliga": 1865, "Serie A": 1855, "Ligue 1": 1815,
    "Eredivisie": 1710, "Primeira Liga": 1700, "Championship": 1660, "Saudi Pro League": 1640,
    "Brasileirão": 1680, "Liga MX": 1640, "Liga Argentina": 1650, "Turkish Super Lig": 1650,
    "Belgian Pro League": 1605, "Scottish Premiership": 1600, "MLS": 1570, "J1 League": 1580,
    "K League 1": 1575, "A-League": 1510, "Serie B": 1515, "2. Bundesliga": 1540,
    "LaLiga 2": 1510, "Ligue 2": 1470, "League One": 1410, "League Two": 1270,
}

CCODE_COUNTRY = {
    "ENG":"England","SCO":"Scotland","WAL":"Wales","NIR":"Northern Ireland","ESP":"Spain",
    "GER":"Germany","ITA":"Italy","FRA":"France","NED":"Netherlands","POR":"Portugal",
    "BEL":"Belgium","TUR":"Türkiye","USA":"United States","CAN":"Canada","MEX":"Mexico",
    "BRA":"Brazil","ARG":"Argentina","SAU":"Saudi Arabia","JPN":"Japan","KOR":"South Korea",
    "AUS":"Australia","COL":"Colombia","CHI":"Chile","AUT":"Austria","SUI":"Switzerland",
    "CRO":"Croatia","POL":"Poland","CZE":"Czechia","DNK":"Denmark","SWE":"Sweden",
    "NOR":"Norway","GRC":"Greece","ROU":"Romania","SRB":"Serbia","ISR":"Israel",
    "IRL":"Ireland","NZL":"New Zealand","KUW":"Kuwait","UGA":"Uganda","ZAF":"South Africa",
    "EGY":"Egypt","QAT":"Qatar","UAE":"United Arab Emirates","CHN":"China","THA":"Thailand",
    "VNM":"Vietnam","INT":"International",
}


def get(url, params=None, timeout=10, tries=1):
    key = (url, tuple(sorted((params or {}).items())))
    if key in CACHE:
        return CACHE[key]
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEAD, timeout=timeout)
            if r.ok:
                ctype = (r.headers.get("content-type") or "").lower()
                if "json" in ctype:
                    value = r.json()
                else:
                    text = r.text
                    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', text, re.S)
                    if not m:
                        m = re.search(r'<script[^>]*>\s*window\.__NEXT_DATA__\s*=\s*(\{.*?\})\s*</script>', text, re.S)
                    if not m:
                        raise RuntimeError("HTML returned without __NEXT_DATA__")
                    value = json.loads(m.group(1))
                CACHE[key] = value
                return value
            last = f"HTTP {r.status_code}"
        except Exception as exc:
            last = str(exc)
        if attempt + 1 < tries:
            time.sleep(0.4)
    raise RuntimeError(last or "request failed")


def first_working(candidates, label):
    errors=[]
    for url, params in candidates:
        try:
            return get(url, params)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError(label + " failed: " + " | ".join(errors))


def page_payload(url):
    return get(url, None, timeout=25, tries=2)


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def pick(obj, *keys):
    if not isinstance(obj, dict):
        return None
    for key in keys:
        value = obj.get(key)
        if value not in (None, ""):
            return value
    return None


def as_num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def country_name(country="", ccode=""):
    if isinstance(country, dict):
        country = country.get("name") or country.get("countryName") or ""
    country = str(country or "").strip()
    code = str(ccode or "").upper().strip()
    return country or CCODE_COUNTRY.get(code) or ("International" if code == "INT" else "Unknown")


def flag(code, country=""):
    code = str(code or "").upper()
    # ISO alpha-2 flags. FotMob commonly gives alpha-3 ccode.
    iso = {
        "ENG":"gb","SCO":"gb-sct","WAL":"gb-wls","NIR":"gb-nir","ESP":"es","GER":"de","ITA":"it",
        "FRA":"fr","NED":"nl","POR":"pt","BEL":"be","TUR":"tr","USA":"us","CAN":"ca","MEX":"mx",
        "BRA":"br","ARG":"ar","SAU":"sa","JPN":"jp","KOR":"kr","AUS":"au","COL":"co","CHI":"cl",
        "AUT":"at","SUI":"ch","CRO":"hr","POL":"pl","CZE":"cz","DNK":"dk","SWE":"se","NOR":"no",
        "GRC":"gr","ROU":"ro","SRB":"rs","ISR":"il","IRL":"ie","NZL":"nz","KUW":"kw","UGA":"ug",
        "ZAF":"za","EGY":"eg","QAT":"qa","UAE":"ae","CHN":"cn","THA":"th","VNM":"vn",
    }.get(code)
    if not iso:
        return "🌍"
    if "-" in iso:
        return "🏴"
    return "".join(chr(127397 + ord(ch)) for ch in iso.upper())


def normalize_comp(name, ccode="", country=""):
    raw = str(name or "").strip()
    aliases = {
        "Champions League":"UEFA Champions League",
        "Europa League":"UEFA Europa League",
        "Conference League":"UEFA Conference League",
        "Champions League Qualification":"UEFA Champions League Qualification",
        "Europa League Qualification":"UEFA Europa League Qualification",
        "Conference League Qualification":"UEFA Conference League Qualification",
    }
    base = aliases.get(raw, raw)
    c = country_name(country, ccode)
    # Country is part of the identity. This prevents Kuwait Premier League from becoming England.
    display = f"{c} {base}" if base == "Premier League" else base
    return base, display, c


def daily(day):
    date = day.strftime("%Y%m%d")
    return first_working([
        (f"{ROOT}/api/data/matches", {"date": date, "timezone": "America/New_York"}),
        (f"{ROOT}/api/data/matches", {"date": date}),
        (f"{ROOT}/api/matches", {"date": date, "timezone": "America/New_York"}),
        (f"{ROOT}/api/matches", {"date": date}),
    ], f"FotMob daily {date}")


def match_details(match_id, slug="match-details"):
    key = str(match_id)
    if key not in DETAIL_CACHE:
        DETAIL_CACHE[key] = first_working([
            (f"{ROOT}/api/data/matchDetails", {"matchId": key}),
            (f"{ROOT}/api/matchDetails", {"matchId": key}),
            (f"{ROOT}/matches/{key}/{slug}", None),
        ], f"match details {key}")
    return DETAIL_CACHE[key]


def team_payload(team_id):
    key = str(team_id)
    if key not in TEAM_CACHE:
        TEAM_CACHE[key] = first_working([
            (f"{ROOT}/api/data/teams", {"id": key}),
            (f"{ROOT}/api/teams", {"id": key}),
        ], f"team {key}")
    return TEAM_CACHE[key]


def league_payload(league_id):
    key = str(league_id)
    if not league_id:
        return {}
    if key not in LEAGUE_CACHE:
        LEAGUE_CACHE[key] = first_working([
            (f"{ROOT}/api/data/leagues", {"id": key}),
            (f"{ROOT}/api/leagues", {"id": key}),
        ], f"league {key}")
    return LEAGUE_CACHE[key]


def match_rows(day_payload):
    out = []
    for league in day_payload.get("leagues", []) if isinstance(day_payload, dict) else []:
        if not isinstance(league, dict):
            continue
        lname = pick(league, "name", "leagueName") or "Competition"
        ccode = pick(league, "ccode", "countryCode") or "INT"
        ctry = country_name(league.get("country"), ccode)
        for match in league.get("matches", []) or []:
            if not isinstance(match, dict):
                continue
            match = dict(match)
            match["_league_name"] = lname
            match["_ccode"] = ccode
            match["_country"] = ctry
            match["_league_id"] = league.get("id") or league.get("primaryId")
            out.append(match)
    return out


def status(match):
    s = match.get("status") or {}
    if s.get("started") and not s.get("finished"):
        return "LIVE"
    if s.get("finished"):
        return "FT"
    return "UPCOMING"


def score(match):
    h = match.get("home") or {}
    a = match.get("away") or {}
    hs, ass = pick(h, "score", "goals"), pick(a, "score", "goals")
    if hs is None or ass is None:
        text = str(pick(match.get("status") or {}, "scoreStr") or "")
        found = re.match(r"\s*(\d+)\s*[-:]\s*(\d+)", text)
        if found:
            hs, ass = int(found.group(1)), int(found.group(2))
    return hs, ass


def current_league(payload):
    # FotMob's team overview exposes the primary/current competition explicitly.
    # Prefer that over whatever competition the next fixture happens to be in.
    for obj in walk(payload):
        if not isinstance(obj,dict): continue
        lid=pick(obj,"primaryLeagueId","leagueId")
        lname=pick(obj,"primaryLeagueName","leagueName")
        if lid and lname:
            season=str(pick(obj,"latestSeason","season","selectedSeason") or "")
            if not season or "2026" in season:
                return {"division":lname,"leagueId":lid,"ccode":pick(obj,"ccode","countryCode","country")}
    # Team overview table format: table -> data -> leagueName/leagueId.
    for obj in walk(payload):
        if not isinstance(obj,dict): continue
        data=obj.get("data")
        if isinstance(data,dict):
            lid=pick(data,"leagueId","primaryLeagueId"); lname=pick(data,"leagueName","primaryLeagueName")
            if lid and lname:
                return {"division":lname,"leagueId":lid,"ccode":pick(data,"ccode","countryCode")}
    for obj in walk(payload):
        if not isinstance(obj,dict): continue
        lid=pick(obj,"leagueId"); lname=pick(obj,"leagueName")
        if lid and lname:
            return {"division":lname,"leagueId":lid,"ccode":pick(obj,"ccode","countryCode")}
    return {"division":None,"leagueId":None,"ccode":None}


def table_position(payload, team_id):
    for obj in walk(payload):
        if not isinstance(obj, dict):
            continue
        tid = obj.get("id") or obj.get("teamId")
        if tid is None or str(tid) != str(team_id):
            continue
        p = pick(obj, "idx", "position", "rank")
        if isinstance(p, (int, float)):
            return int(p)
    return None



def historical_position(league_id, team_id):
    if not league_id or not team_id:
        return None
    for season in ("2025/2026", "2025"):
        try:
            payload = first_working([(f"{ROOT}/api/data/leagues", {"id": str(league_id), "season": season}), (f"{ROOT}/api/leagues", {"id": str(league_id), "season": season})], f"historical league {league_id} {season}")
            pos = table_position(payload, team_id)
            if pos is not None:
                return pos
        except Exception as exc:
            print("Historical league lookup failed", league_id, season, exc)
    return None

def form_from_team(payload, team_id):
    rows = []
    for obj in walk(payload):
        if not isinstance(obj, dict):
            continue
        h = obj.get("home") or obj.get("homeTeam")
        a = obj.get("away") or obj.get("awayTeam")
        if not isinstance(h, dict) or not isinstance(a, dict):
            continue
        hs, ass = pick(h, "score", "goals"), pick(a, "score", "goals")
        hid, aid = pick(h, "id", "teamId"), pick(a, "id", "teamId")
        if hs is None or ass is None or hid is None or aid is None:
            continue
        try:
            hs, ass = int(hs), int(ass)
        except (TypeError, ValueError):
            continue
        if str(team_id) == str(hid):
            rows.append("W" if hs > ass else "D" if hs == ass else "L")
        elif str(team_id) == str(aid):
            rows.append("W" if ass > hs else "D" if hs == ass else "L")
    return "".join(rows[-5:])


def previous_finish(payload, team_id):
    # Prefer explicit 2025/26 historical tables in the team payload.
    best = None
    for obj in walk(payload):
        if not isinstance(obj, dict):
            continue
        season = str(pick(obj, "season", "selectedSeason", "year") or "")
        if not re.search(r"2025(?:/2026)?|25/26", season, re.I):
            continue
        tid = obj.get("id") or obj.get("teamId")
        if tid is not None and str(tid) == str(team_id):
            p = pick(obj, "idx", "position", "rank", "finalPosition")
            if isinstance(p, (int, float)):
                best = int(p)
    if best is not None:
        return best
    return None


def transfer_impact(payload):
    # Bounded rough squad-change signal. It is deliberately small versus division strength.
    incoming = outgoing = 0
    for obj in walk(payload):
        if not isinstance(obj, dict):
            continue
        key = str(pick(obj, "name", "title", "header") or "").lower()
        items = obj.get("items")
        if not isinstance(items, list):
            continue
        if any(k in key for k in ("incoming", "arrival", "transfer in")):
            incoming += len(items)
        elif any(k in key for k in ("outgoing", "departure", "transfer out")):
            outgoing += len(items)
    return round(max(-7, min(7, (incoming - outgoing) * 0.45)), 1)


def lineup(detail, home_id, away_id):
    result={str(home_id):[],str(away_id):[]}
    candidates=[]
    for obj in walk(detail):
        if not isinstance(obj,dict): continue
        arr=obj.get("lineups")
        if isinstance(arr,list): candidates.extend(arr)
        if obj.get("teamId") and (obj.get("players") or obj.get("starters")):
            candidates.append(obj)
    for team in candidates:
        tid=pick(team,"teamId","id")
        if tid is None or str(tid) not in result: continue
        players=[]
        for key in ("players","starters","lineup"):
            arr=team.get(key)
            if isinstance(arr,list): players.extend(arr)
        for player in players:
            if not isinstance(player,dict): continue
            p=player.get("player") if isinstance(player.get("player"),dict) else player
            name=pick(p,"name","playerName")
            if not name: continue
            rating=pick(player,"rating","matchRating","avgRating","averageRating","seasonRating")
            if isinstance(rating,dict): rating=pick(rating,"num","value")
            result[str(tid)].append({
                "name":name,
                "position":pick(player,"position","role","positionName","usualPosition") or pick(p,"position","role","usualPosition"),
                "rating":rating,
                "starter":player.get("starter", player.get("isSubstitute") is not True),
            })
    for key in result:
        seen=set();clean=[]
        for p in result[key]:
            if p["name"] in seen:continue
            seen.add(p["name"]);clean.append(p)
        result[key]=clean[:20]
    return result[str(home_id)],result[str(away_id)]


def xg(detail):
    vals=None
    for obj in walk(detail):
        if not isinstance(obj,dict): continue
        title=str(pick(obj,"title","name") or "").lower()
        if "expected goals" not in title and title not in ("xg","expected goals (xg)"): continue
        raw=obj.get("stats")
        if isinstance(raw,list):
            nums=[as_num(x) for x in raw]
            nums=[x for x in nums if x is not None]
            if len(nums)>=2: return nums[0],nums[1]
        if isinstance(raw,dict):
            pair=raw.get("stats") or raw.get("values")
            if isinstance(pair,list):
                nums=[as_num(x) for x in pair]
                nums=[x for x in nums if x is not None]
                if len(nums)>=2:return nums[0],nums[1]
    # Some match payloads put the entire stat entry one level deeper.
    for obj in walk(detail):
        if not isinstance(obj,dict): continue
        if str(pick(obj,"key","title") or "").lower() in ("expectedgoals","xg","expected_goals"):
            raw=obj.get("stats")
            if isinstance(raw,list) and len(raw)>=2:
                nums=[as_num(x) for x in raw]
                if all(x is not None for x in nums[:2]): return nums[0],nums[1]
    return None,None


def h2h(detail):
    for obj in walk(detail):
        if not isinstance(obj, dict):
            continue
        h = obj.get("h2h")
        if isinstance(h, dict):
            for key in ("summary", "form", "results"):
                value = h.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, list) and len(value) >= 3:
                    return f"{value[0]}–{value[1]}–{value[2]}"
    return "Not available from FotMob."


def poisson(lam, max_goals=7):
    p=[math.exp(-lam)]
    for k in range(1,max_goals+1): p.append(p[-1]*lam/k)
    return p


def safe_mean(vals, default=None):
    vals=[float(x) for x in vals if isinstance(x,(int,float))]
    return (sum(vals)/len(vals)) if vals else default


def recent_stats(payload, team_id, n=8):
    games=[]
    for obj in walk(payload):
        if not isinstance(obj,dict): continue
        h=obj.get("home") or obj.get("homeTeam"); a=obj.get("away") or obj.get("awayTeam")
        if not isinstance(h,dict) or not isinstance(a,dict): continue
        hid=pick(h,"id","teamId"); aid=pick(a,"id","teamId")
        hs=as_num(pick(h,"score","goals")); ass=as_num(pick(a,"score","goals"))
        if hs is None or ass is None or (str(hid)!=str(team_id) and str(aid)!=str(team_id)): continue
        home=str(hid)==str(team_id)
        gf,ga=(hs,ass) if home else (ass,hs)
        result="W" if gf>ga else "D" if gf==ga else "L"
        games.append({"gf":gf,"ga":ga,"result":result,"home":home})
    games=games[-n:]
    pts=sum(3 if g["result"]=="W" else 1 if g["result"]=="D" else 0 for g in games)
    return {"games":games,"form":"".join(g["result"] for g in games),"points":pts,
            "gf":safe_mean([g["gf"] for g in games],1.35),"ga":safe_mean([g["ga"] for g in games],1.35),
            "home":[g for g in games if g["home"]],"away":[g for g in games if not g["home"]]}


def player_quality(line):
    vals=[]
    for p in line or []:
        for k in ("seasonRating","rating","avgRating","averageRating","matchRating"):
            v=as_num(p.get(k))
            if v is not None and 5<=v<=10:
                vals.append(v); break
    return safe_mean(vals,None)


def lineup_stats(line):
    starters=[p for p in line or [] if p.get("starter",True)]
    bench=[p for p in line or [] if not p.get("starter",True)]
    return {"starters":len(starters),"bench":len(bench),"avgRating":player_quality(starters),
            "players":[p.get("name") for p in starters if p.get("name")][:11]}


def extract_injuries(payload):
    out=[]
    for obj in walk(payload):
        if not isinstance(obj,dict): continue
        status=str(pick(obj,"status","injuryStatus","availability") or "").lower()
        injury=pick(obj,"injury","injuryType","reason")
        name=pick(obj,"name","playerName")
        if name and (injury or any(x in status for x in ("injur","out","suspend","doubt"))):
            out.append({"name":name,"status":injury or status})
    seen=set(); clean=[]
    for x in out:
        if x["name"] in seen: continue
        seen.add(x["name"]); clean.append(x)
    return clean[:12]


def extract_team_xg(payload, team_id):
    vals=[]
    for obj in walk(payload):
        if not isinstance(obj,dict): continue
        # Recent match stat blocks sometimes contain xG under a team id/name pair.
        title=str(pick(obj,"title","name","key") or "").lower()
        if "expected goals" not in title and title not in ("xg","expected goals (xg)"): continue
        v=obj.get("stats") or obj.get("values") or obj.get("value")
        if isinstance(v,list):
            vals += [as_num(x) for x in v if as_num(x) is not None]
        elif as_num(v) is not None: vals.append(as_num(v))
    return safe_mean(vals,None)


def h2h_detail(detail, home_id, away_id):
    # Return structured recent H2H when available, not just an opaque string.
    records=[]
    for obj in walk(detail):
        if not isinstance(obj,dict): continue
        h=obj.get("h2h")
        if not isinstance(h,dict): continue
        for key in ("matches","results","games"):
            arr=h.get(key)
            if not isinstance(arr,list): continue
            for g in arr[:10]:
                if not isinstance(g,dict): continue
                home=g.get("home") or g.get("homeTeam") or {}
                away=g.get("away") or g.get("awayTeam") or {}
                hid=pick(home,"id","teamId"); aid=pick(away,"id","teamId")
                hs=as_num(pick(home,"score","goals")); ass=as_num(pick(away,"score","goals"))
                if hs is None or ass is None: continue
                if {str(hid),str(aid)}=={str(home_id),str(away_id)}:
                    records.append((str(hid)==str(home_id),hs,ass))
    if records:
        hp=ap=dp=0
        for home_side,hs,ass in records:
            home_goals,away_goals=(hs,ass) if home_side else (ass,hs)
            if home_goals>away_goals: hp+=1
            elif home_goals<away_goals: ap+=1
            else: dp+=1
        return {"games":len(records),"homeWins":hp,"draws":dp,"awayWins":ap,
                "avgHomeGoals":round(safe_mean([(x[1] if x[0] else x[2]) for x in records],0),2),
                "avgAwayGoals":round(safe_mean([(x[2] if x[0] else x[1]) for x in records],0),2)},
    return {"games":0,"homeWins":0,"draws":0,"awayWins":0}


def league_strength(name):
    base=str(name or "")
    if base.endswith(" Premier League") or base=="Premier League":
        if base in ("Premier League","England Premier League"): return 1885
        return 1510
    return STRENGTH.get(base,1500)


def model(match):
    h,a=match["homeData"],match["awayData"]
    hd,ad=h.get("division"),a.get("division")
    same=bool(hd and ad and hd==ad)
    factors=[]
    # Strength baseline is deliberately dominant early in a season.
    strength=(league_strength(hd)-league_strength(ad))/24.0
    score= strength; factors.append(["Division strength",strength])
    # Last season finish is only comparable within same division; cross-division is ignored.
    if same and h.get("lastSeasonPosition") and a.get("lastSeasonPosition"):
        v=(a["lastSeasonPosition"]-h["lastSeasonPosition"])*1.8; score+=v; factors.append(["Last-season finish",v])
    else: factors.append(["Last-season finish",0])
    if same and h.get("position") and a.get("position"):
        v=(a["position"]-h["position"])*1.2; score+=v; factors.append(["Current table",v])
    else: factors.append(["Current table",0])
    # Form: points + goal difference, with home/away split.
    fp=(h.get("formPoints",0)-a.get("formPoints",0))*0.75
    gd=(h.get("recentGF",1.35)-h.get("recentGA",1.35))-(a.get("recentGF",1.35)-a.get("recentGA",1.35))
    v=fp+gd*2.0; score+=v; factors.append(["Recent form / goal diff",v])
    # Attack/defence rates influence both direction and total goals.
    atk=(h.get("recentGF",1.35)-a.get("recentGA",1.35))-(a.get("recentGF",1.35)-h.get("recentGA",1.35))
    score += atk*2.8; factors.append(["Attack vs defence",atk*2.8])
    # xG if match/team data supplies it.
    if h.get("xg") is not None and a.get("xg") is not None:
        v=(h["xg"]-a["xg"])*8.0; score+=v; factors.append(["xG",v])
    else: factors.append(["xG",0])
    # Lineup quality/availability only matters when we actually have data.
    lq=(h.get("lineupAvgRating") or 0)-(a.get("lineupAvgRating") or 0)
    v=lq*8.5; score+=v; factors.append(["Starting XI quality",v])
    av=(len(a.get("injuries",[]))-len(h.get("injuries",[])))*0.7; score+=av; factors.append(["Availability",av])
    tr=(h.get("transferImpact") or 0)-(a.get("transferImpact") or 0); score+=tr*0.7; factors.append(["Squad change",tr*0.7])
    hh=match.get("h2h") or {}
    if hh.get("games"):
        v=((hh.get("homeWins",0)-hh.get("awayWins",0))/hh["games"])*4; score+=v; factors.append(["H2H",v])
    else: factors.append(["H2H",0])
    # Home advantage is small, not enough to make every home team win.
    score += 3.5; factors.append(["Home advantage",3.5])

    # Build expected goals from team scoring/allowing rates. This fixes the old
    # "verdict says win, score says draw" contradiction by deriving both from one grid.
    h_attack=h.get("recentGF",1.35); h_def=h.get("recentGA",1.35)
    a_attack=a.get("recentGF",1.35); a_def=a.get("recentGA",1.35)
    base_total=2.55
    lam_h=0.52*h_attack+0.48*a_def+0.18
    lam_a=0.52*a_attack+0.48*h_def-0.02
    if h.get("xg") is not None: lam_h=0.72*lam_h+0.28*max(.3,min(3.4,h["xg"]))
    if a.get("xg") is not None: lam_a=0.72*lam_a+0.28*max(.25,min(3.2,a["xg"]))
    # Apply directional model signal without exploding goal totals.
    shift=max(-0.55,min(0.55,score/100))
    lam_h += shift; lam_a -= shift
    # Normalize toward competition scoring environment.
    total=max(1.75,min(3.35,lam_h+lam_a))
    scale=base_total/total
    lam_h=max(.25,min(3.6,lam_h*scale)); lam_a=max(.2,min(3.2,lam_a*scale))

    ph,pa=poisson(lam_h),poisson(lam_a)
    grid=[]; pH=pD=pA=0
    for i,pi in enumerate(ph):
        for j,pj in enumerate(pa):
            q=pi*pj; grid.append((q,i,j))
            if i>j:pH+=q
            elif i==j:pD+=q
            else:pA+=q
    probs=[pH,pD,pA]; sm=sum(probs); probs=[x/sm for x in probs]
    idx=max(range(3),key=lambda i:probs[i])
    verdict=match["home"] if idx==0 else "DRAW" if idx==1 else match["away"]
    # Pick the most probable exact score INSIDE the winning outcome, so the
    # verdict and score can never contradict each other.
    allowed={0:lambda i,j:i>j,1:lambda i,j:i==j,2:lambda i,j:i<j}[idx]
    modal=max((x for x in grid if allowed(x[1],x[2])),key=lambda x:x[0])
    projected=f"{modal[1]}–{modal[2]}"
    confidence=round(max(45,min(92,50+(sorted(probs,reverse=True)[0]-sorted(probs,reverse=True)[1])*145)))
    comp=30
    comp += 8 if hd else 0; comp += 8 if ad else 0; comp += 7 if h.get("form") else 0; comp += 7 if a.get("form") else 0
    comp += 8 if h.get("lastSeasonPosition") is not None and a.get("lastSeasonPosition") is not None else 0
    comp += 8 if h.get("xg") is not None and a.get("xg") is not None else 0
    comp += 10 if h.get("lineup") and a.get("lineup") else 0
    comp += 7 if hh.get("games") else 0
    return {"verdict":f"WIN: {verdict}" if verdict!="DRAW" else "DRAW","confidence":confidence,
            "probabilities":[round(x,4) for x in probs],"projected":projected,
            "modalScore":projected,"expectedGoals":[round(lam_h,2),round(lam_a,2)],
            "factors":[[n,round(v,2)] for n,v in factors],"dataCompleteness":min(100,comp),
            "decisionNote":"Unified probability + score model. Division strength, recent performance, xG, XI quality, availability, squad change, H2H and home advantage are weighted by evidence quality."}


def parallel_fetch(ids, fn, workers=8, label="items"):
    """Fetch unique IDs concurrently. Failed items are returned as empty dicts so one bad
    FotMob response cannot stall the entire matchday."""
    ids=[x for x in dict.fromkeys(str(i) for i in ids if i not in (None, ""))]
    out={}
    if not ids: return out
    print(f"FETCH {label}: {len(ids)} unique with {min(workers,len(ids))} workers")
    with ThreadPoolExecutor(max_workers=min(workers,len(ids))) as ex:
        futures={ex.submit(fn,i):i for i in ids}
        done=0
        for fut in as_completed(futures):
            i=futures[fut]
            try: out[i]=fut.result()
            except Exception as exc:
                out[i]={}
                print(f"WARN {label} {i}: {exc}")
            done+=1
            if done%10==0 or done==len(ids): print(f"PROGRESS {label}: {done}/{len(ids)}")
    return out


def main():
    now = dt.datetime.now(dt.timezone.utc).astimezone(TZ)
    days = [now.date(), now.date() + dt.timedelta(days=1)]
    raw, errors = [], []
    for day in days:
        try:
            payload = daily(day)
            rows = match_rows(payload)
            print(f"FotMob {day}: {len(rows)} raw fixtures")
            raw.extend(rows)
        except Exception as exc:
            errors.append(f"{day}: {exc}")
            print("FotMob daily failed", day, exc)

    matches0, seen = [], set()
    for m in raw:
        mid = str(pick(m, "id", "matchId") or "")
        if not mid or mid in seen: continue
        seen.add(mid)
        home, away = m.get("home") or {}, m.get("away") or {}
        hn, an = pick(home, "name", "longName"), pick(away, "name", "longName")
        if not hn or not an: continue
        base_comp, display_comp, ctry = normalize_comp(m.get("_league_name"), m.get("_ccode"), m.get("_country"))
        if base_comp not in SUPPORTED: continue
        m["_base_comp"], m["_display_comp"], m["_country"] = base_comp, display_comp, ctry
        matches0.append(m)

    print(f"SUPPORTED FIXTURES: {len(matches0)}")
    team_ids=[]
    for m in matches0:
        team_ids.extend([m.get("home",{}).get("id"),m.get("away",{}).get("id")])
    teams=parallel_fetch(team_ids, lambda tid: team_payload(tid), workers=10, label="teams")

    # Resolve each club's CURRENT domestic league from its own team payload.
    league_ids=[]
    current={}
    for tid,payload in teams.items():
        cur=current_league(payload)
        current[tid]=cur
        if cur.get("leagueId"): league_ids.append(cur["leagueId"])
    leagues=parallel_fetch(league_ids, lambda lid: league_payload(lid), workers=10, label="leagues")

    # Match details are the expensive/deep part. Fetch them concurrently. We fetch
    # every upcoming/live match, and only finished matches that have no existing data.
    details_ids=[]
    for m in matches0:
        st=m.get("status") or {}
        if st.get("started") and not st.get("finished"):
            details_ids.append(m.get("id"))
        elif not st.get("finished"):
            details_ids.append(m.get("id"))
    details=parallel_fetch(details_ids, lambda mid: match_details(mid), workers=8, label="match-details")

    matches=[]
    for m in matches0:
        mid=str(pick(m,"id","matchId")); home=m.get("home") or {}; away=m.get("away") or {}
        hn,an=pick(home,"name","longName"),pick(away,"name","longName")
        hp=teams.get(str(home.get("id")),{}); ap=teams.get(str(away.get("id")),{})
        hl=current.get(str(home.get("id")),{}); al=current.get(str(away.get("id")),{})
        hleague=leagues.get(str(hl.get("leagueId")),{}); aleague=leagues.get(str(al.get("leagueId")),{})
        hpos=table_position(hleague,home.get("id")) or table_position(hp,home.get("id"))
        apos=table_position(aleague,away.get("id")) or table_position(ap,away.get("id"))
        hlast=previous_finish(hp,home.get("id")) or historical_position(hl.get("leagueId"),home.get("id"))
        alast=previous_finish(ap,away.get("id")) or historical_position(al.get("leagueId"),away.get("id"))
        hr=recent_stats(hp,home.get("id")); ar=recent_stats(ap,away.get("id"))
        hd={"id":home.get("id"),"division":hl.get("division"),"leagueId":hl.get("leagueId"),"ccode":hl.get("ccode"),"position":hpos,
            "form":form_from_team(hp,home.get("id")),"lastSeasonPosition":hlast,"transferImpact":transfer_impact(hp),"lineup":[],"injuries":extract_injuries(hp),
            "recentGF":hr["gf"],"recentGA":hr["ga"],"recentHomeGF":safe_mean([g["gf"] for g in hr["home"]],None),"recentHomeGA":safe_mean([g["ga"] for g in hr["home"]],None)}
        ad={"id":away.get("id"),"division":al.get("division"),"leagueId":al.get("leagueId"),"ccode":al.get("ccode"),"position":apos,
            "form":form_from_team(ap,away.get("id")),"lastSeasonPosition":alast,"transferImpact":transfer_impact(ap),"lineup":[],"injuries":extract_injuries(ap),
            "recentGF":ar["gf"],"recentGA":ar["ga"],"recentAwayGF":safe_mean([g["gf"] for g in ar["away"]],None),"recentAwayGA":safe_mean([g["ga"] for g in ar["away"]],None)}
        hd["formPoints"]=sum(3 if x=="W" else 1 if x=="D" else 0 for x in hd["form"]); ad["formPoints"]=sum(3 if x=="W" else 1 if x=="D" else 0 for x in ad["form"])
        detail=details.get(mid,{})
        try:
            hd["lineup"],ad["lineup"]=lineup(detail,hd["id"],ad["id"])
            hsx,asx=lineup_stats(hd["lineup"]),lineup_stats(ad["lineup"])
            hd["lineupAvgRating"],ad["lineupAvgRating"]=hsx["avgRating"],asx["avgRating"]
            hd["lineupStarters"],ad["lineupStarters"]=hsx["starters"],asx["starters"]
            hd["injuries"]=hd["injuries"] or extract_injuries(detail); ad["injuries"]=ad["injuries"] or extract_injuries(detail)
            hd["xg"],ad["xg"]=xg(detail); hh=h2h_detail(detail,hd["id"],ad["id"]); h2h_summary=h2h(detail)
        except Exception as exc:
            print("Detail parse failed",mid,exc); hh={"games":0}; h2h_summary="Not available from FotMob."; hd["xg"]=ad["xg"]=None; hd["lineupAvgRating"]=ad["lineupAvgRating"]=None
        hs,ass=score(m); st=m.get("status") or {}
        out={"id":mid,"competition":m["_display_comp"],"competitionName":m["_base_comp"],"competitionCountry":m["_country"],
             "competitionCode":str(m.get("_ccode") or "INT").upper(),"competitionFlag":flag(m.get("_ccode"),m["_country"]),"home":hn,"away":an,
             "homeScore":hs,"awayScore":ass,"status":status(m),"kickoff":st.get("utcTime") or m.get("utcTime"),"minute":{"short":pick(st,"reason","period") or ""},
             "homeData":hd,"awayData":ad,"h2hSummary":h2h_summary,"h2h":hh,"fotmobMatchUrl":f"{ROOT}/matches/{mid}/match-details"}
        out["model"]=model(out); matches.append(out)

    matches.sort(key=lambda x:(x["status"]!="LIVE",x.get("kickoff") or ""))
    if not matches:
        print("NO NEW FIXTURES GENERATED")
        if errors: print("SOURCE ERRORS:"," | ".join(errors))
        existing=Path("data/fixtures.json")
        if existing.exists():
            try:
                old=json.loads(existing.read_text(encoding="utf-8"))
                if isinstance(old.get("matches"),list) and old["matches"]:
                    print("KEEPING LAST VALID FEED:",len(old["matches"]),"fixtures"); old["sourceStatus"]="FotMob temporarily unavailable · last valid feed retained"; old["sourceErrors"]=errors; old["updatedAt"]=dt.datetime.now(dt.timezone.utc).isoformat(); existing.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding="utf-8"); return
            except Exception as exc: print("Could not preserve previous feed:",exc)
        raise SystemExit(2)
    result={"updatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"fixtureCount":len(matches),"sourceStatus":f"FotMob only · {len(matches)} fixtures","sourceErrors":errors,"matches":matches}
    Path("data").mkdir(exist_ok=True); Path("data/fixtures.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    enriched=sum(1 for m in matches if m.get("homeData",{}).get("division") and m.get("awayData",{}).get("division"))
    lineups=sum(1 for m in matches if m.get("homeData",{}).get("lineup") and m.get("awayData",{}).get("lineup"))
    xgpairs=sum(1 for m in matches if m.get("homeData",{}).get("xg") is not None and m.get("awayData",{}).get("xg") is not None)
    h2hs=sum(1 for m in matches if m.get("h2h",{}).get("games",0)); forms=sum(1 for m in matches if m.get("homeData",{}).get("form") and m.get("awayData",{}).get("form"))
    print("WROTE",len(matches),"fixtures | divisions",enriched,"| form pairs",forms,"| lineups",lineups,"| xG pairs",xgpairs,"| H2H",h2hs)


if __name__ == "__main__":
    main()
