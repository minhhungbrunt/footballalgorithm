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
SOFA = "https://www.sofascore.com/api/v1"
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
SOFA_CACHE = {}
SOFA_EVENTS = {}
PLAYER_CACHE = {}

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
    "U.S. Open Cup", "CONCACAF Champions Cup", "Copa do Brasil", "Colombian Primera A", "Ecuador Serie A",
}

# Broad structural priors. These are not betting odds.
STRENGTH = {
    "Premier League": 1885, "UEFA Champions League": 1890, "Champions League": 1890,
    "LaLiga": 1870, "Bundesliga": 1865, "Serie A": 1855, "Ligue 1": 1815,
    "Eredivisie": 1710, "Primeira Liga": 1700, "Championship": 1660, "Saudi Pro League": 1640,
    "Brasileirão": 1680, "Liga MX": 1640, "Liga Argentina": 1650, "Turkish Super Lig": 1650,
    "Belgian Pro League": 1605, "Scottish Premiership": 1600, "MLS": 1570, "J1 League": 1580,
    "K League 1": 1575, "A-League": 1510, "Ecuador Serie A": 1545, "German Bundesliga": 1765, "Austrian Bundesliga": 1610, "Serie B": 1515, "2. Bundesliga": 1540,
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
    "VNM":"Vietnam","ECU":"Ecuador","INT":"International",
}


def get(url, params=None, timeout=10, tries=2):
    key = (url, tuple(sorted((params or {}).items())))
    if key in CACHE:
        return CACHE[key]
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEAD, timeout=timeout)
            if r.ok:
                value = r.json()
                CACHE[key] = value
                return value
            last = f"HTTP {r.status_code}"
        except Exception as exc:
            last = str(exc)
        if attempt + 1 < tries:
            time.sleep(0.35 + attempt * 0.35)
    raise RuntimeError(last or "request failed")


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
        "ZAF":"za","EGY":"eg","QAT":"qa","UAE":"ae","CHN":"cn","THA":"th","VNM":"vn","ECU":"ec",
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
    }
    base = aliases.get(raw, raw)
    c = country_name(country, ccode)
    low = base.lower()

    # Normalize generic league names first, then ALWAYS qualify domestic
    # competitions by country. This prevents e.g. England League One and
    # Scotland League One from becoming one shared league.
    if low in {"bundesliga", "austrian bundesliga", "österreichische bundesliga"}:
        base = "Austrian Bundesliga" if c == "Austria" else "German Bundesliga" if c == "Germany" else "Bundesliga"
    elif low in {"serie a", "liga pro serie a", "ligapro serie a",
                 "liga pro ecuador", "serie a de ecuador"}:
        base = "Ecuador Serie A" if c == "Ecuador" else "Serie A"
    elif low in {"league one", "english league one", "scottish league one"}:
        base = "League One"
    elif low in {"league two", "english league two", "scottish league two"}:
        base = "League Two"

    # International competitions keep their canonical global names.
    if base.startswith("UEFA ") or c in ("International","Unknown"):
        display = base
    else:
        display = f"{c} {base}".strip()

    return base, display, c


def sofa_get(path, params=None, timeout=8, tries=2):
    url = SOFA + path
    key = (url, tuple(sorted((params or {}).items())))
    if key in SOFA_CACHE:
        return SOFA_CACHE[key]
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": HEAD["User-Agent"], "Accept":"application/json", "Referer":"https://www.sofascore.com/"}, timeout=timeout)
            if r.ok:
                value = r.json(); SOFA_CACHE[key] = value; return value
            last = f"HTTP {r.status_code}"
        except Exception as exc:
            last = str(exc)
        if attempt + 1 < tries:
            time.sleep(.3 + attempt*.3)
    raise RuntimeError(last or "Sofascore request failed")


def norm_team_name(name):
    x = re.sub(r"[^a-z0-9]", "", str(name or "").lower())
    aliases = {
        "manchesterunited":"manutd", "manchesterunitedfc":"manutd", "manchestercity":"mancity",
        "tottenhamhotspur":"tottenham", "tottenhamhotspurfc":"tottenham", "spurs":"tottenham",
        "wolverhamptonwanderers":"wolves", "wolverhamptonwanderersfc":"wolves",
        "westhamunited":"westham", "westhamunitedfc":"westham", "newcastleunited":"newcastle",
        "nottinghamforest":"nottmforest", "brightonandhovealbion":"brighton", "crystalpalace":"crystalpalace",
        "leedsunited":"leeds", "ipswichtown":"ipswich", "queensparkrangers":"qpr",
        "psveindhoven":"psv", "psveindhoven":"psv", "internazionale":"inter", "intermilan":"inter",
        "atleticomadrid":"atleticomadrid", "atleticomadrids":"atleticomadrid", "parissaintgermain":"psg",
    }
    return aliases.get(x, x)


def sofa_scheduled(day):
    date = day.strftime("%Y-%m-%d")
    payload = sofa_get(f"/sport/football/scheduled-events/{date}")
    events = payload.get("events") if isinstance(payload, dict) else []
    return events if isinstance(events, list) else []


def sofa_event_map(events):
    out={}
    for e in events:
        if not isinstance(e,dict): continue
        h=((e.get("homeTeam") or {}).get("name")); a=((e.get("awayTeam") or {}).get("name"))
        if not h or not a: continue
        out[(norm_team_name(h),norm_team_name(a))]=e
    return out

def sofa_find_event(events, home, away):
    """Tolerant name matching for FotMob ↔ SofaScore team names."""
    hn,an=norm_team_name(home),norm_team_name(away)
    exact=sofa_event_map(events).get((hn,an))
    if exact:return exact
    for e in events:
        if not isinstance(e,dict): continue
        eh=norm_team_name(((e.get("homeTeam") or {}).get("name")))
        ea=norm_team_name(((e.get("awayTeam") or {}).get("name")))
        if not eh or not ea: continue
        if (eh in hn or hn in eh) and (ea in an or an in ea):
            return e
    return None


def sofa_lineups(event_id):
    if not event_id: return {}, {}
    payload=sofa_get(f"/event/{event_id}/lineups")
    result=[]
    for side in ("home","away"):
        block=payload.get(side) if isinstance(payload,dict) else {}
        players=[]
        for row in (block.get("players") or []) if isinstance(block,dict) else []:
            if not isinstance(row,dict): continue
            pl=row.get("player") or {}
            stats=row.get("statistics") or {}
            name=pl.get("name") or row.get("name")
            if not name: continue
            pid=pick(pl,"id","playerId") or pick(row,"playerId","playerID")
            players.append({
                "name":name,"playerId":pid,
                "image":f"https://images.fotmob.com/image_resources/playerimages/{pid}.png" if pid else None,
                "position":row.get("position") or pl.get("position"),
                "rating":stats.get("rating") or row.get("rating"),
                "starter":bool(row.get("substitute") is False or row.get("starter") is True),
                "jersey":row.get("shirtNumber") or pl.get("jerseyNumber"),
            })
        subs=[]
        for row in (block.get("substitutes") or []) if isinstance(block,dict) else []:
            pl=row.get("player") if isinstance(row,dict) else {}
            if not isinstance(pl,dict): pl={}
            name=pl.get("name") or row.get("name") if isinstance(row,dict) else None
            if name: subs.append({"name":name,"position":row.get("position"),"rating":(row.get("statistics") or {}).get("rating"),"starter":False})
        result.append({"players":players,"substitutes":subs,"missingPlayers":block.get("missingPlayers",[]) if isinstance(block,dict) else [],"formation":block.get("formation") if isinstance(block,dict) else None,"confirmed":bool(payload.get("confirmed"))})
    return result[0], result[1]


def sofa_incidents(event_id):
    if not event_id: return []
    payload=sofa_get(f"/event/{event_id}/incidents")
    incidents=payload.get("incidents") if isinstance(payload,dict) else []
    out=[]
    for i in incidents or []:
        if not isinstance(i,dict): continue
        if i.get("incidentType")!="goal": continue
        player=i.get("player") or {}; assist=i.get("assist1") or i.get("assist2") or {}
        pid=pick(player,"id","playerId")
        aid=pick(assist,"id","playerId")
        out.append({"minute":i.get("time"),"added":i.get("addedTime"),
                    "team":"home" if i.get("isHome") else "away",
                    "scorer":player.get("name"),"scorerId":pid,
                    "scorerImage":f"https://images.fotmob.com/image_resources/playerimages/{pid}.png" if pid else None,
                    "assist":assist.get("name"),"assistId":aid,
                    "assistImage":f"https://images.fotmob.com/image_resources/playerimages/{aid}.png" if aid else None,
                    "ownGoal":bool(i.get("incidentClass")=="ownGoal" or i.get("incidentClass")=="missed")})
    return sorted(out,key=lambda x:(x.get("minute") or 0,x.get("added") or 0))


def lineup_quality(block):
    vals=[]
    for p in (block or {}).get("players",[]):
        r=as_num(p.get("rating"))
        if r is not None: vals.append(r)
    return round(sum(vals)/len(vals),2) if vals else None

def daily(day):
    """Fetch a FotMob daily fixture list with endpoint fallbacks.

    FotMob has changed/retired API paths before. The current public route is
    /api/matches; /api/data/matches is retained only as a compatibility fallback.
    We never silently return an empty feed.
    """
    date = day.strftime("%Y%m%d")
    attempts = [
        (f"{ROOT}/api/matches", {"date": date, "timezone": "America/New_York"}),
        (f"{ROOT}/api/matches", {"date": date}),
        (f"{ROOT}/api/data/matches", {"date": date}),
    ]
    errors = []
    for url, params in attempts:
        try:
            payload = get(url, params)
            if isinstance(payload, dict) and payload.get("leagues") is not None:
                return payload
            errors.append(f"{url}: unexpected response")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("FotMob endpoints failed: " + " | ".join(errors))


def match_details(match_id):
    key=str(match_id)
    if key not in DETAIL_CACHE:
        try: DETAIL_CACHE[key]=get(f"{ROOT}/api/data/matchDetails",{"matchId":key})
        except Exception:
            DETAIL_CACHE[key]=get(f"{ROOT}/api/matchDetails",{"matchId":key})
    return DETAIL_CACHE[key]

def team_payload(team_id, name=""):
    key=str(team_id)
    if key not in TEAM_CACHE:
        try: TEAM_CACHE[key]=get(f"{ROOT}/api/data/teams",{"id":key})
        except Exception:
            try: TEAM_CACHE[key]=get(f"{ROOT}/api/teams",{"id":key})
            except Exception:
                TEAM_CACHE[key]={}
    return TEAM_CACHE[key]

def player_payload(player_id):
    key=str(player_id)
    if not player_id:
        return {}
    if key not in PLAYER_CACHE:
        try:
            PLAYER_CACHE[key]=get(f"{ROOT}/api/data/playerData",
                                  {"id":key,"includeMarketValues":"true"})
        except Exception:
            try:
                PLAYER_CACHE[key]=get(f"{ROOT}/api/playerData",
                                      {"id":key,"includeMarketValues":"true"})
            except Exception:
                PLAYER_CACHE[key]={}
    return PLAYER_CACHE[key]


def _money_number(value):
    if isinstance(value, dict):
        for k in ("value","amount","marketValue","estimatedValue"):
            if value.get(k) not in (None, ""):
                n=as_num(value.get(k))
                if n is not None:
                    return n
        return None
    if isinstance(value, (int,float)):
        return float(value)
    s=str(value or "").replace(",","").strip()
    if not s:
        return None
    m=re.search(r'(\d+(?:\.\d+)?)\s*([kKmMbB])?', s)
    if not m:
        return None
    n=float(m.group(1))
    unit=(m.group(2) or "").lower()
    return n * {"k":1e3,"m":1e6,"b":1e9}.get(unit,1)


def player_estimated_value(payload):
    """Current FotMob/SciSports estimated transfer value in euros."""
    if not isinstance(payload,dict):
        return None

    # Prefer explicit current-value fields.
    preferred=("estimatedTransferValue","estimatedValue","etv","marketValue","transferValue")
    for key in preferred:
        if key in payload:
            n=_money_number(payload.get(key))
            if n is not None and n > 0:
                return n

    # Then inspect nested market-value objects, preferring the latest/current entry.
    candidates=[]
    for obj in walk(payload):
        if not isinstance(obj,dict):
            continue
        for key in preferred:
            if key not in obj:
                continue
            n=_money_number(obj.get(key))
            if n is not None and n > 0:
                candidates.append(n)

    if candidates:
        return candidates[-1]
    return None


def squad_value_map(payload):
    """Map FotMob squad player names/IDs to their current estimated value."""
    out={}
    for obj in walk(payload):
        if not isinstance(obj,dict):
            continue
        pid=pick(obj,"playerId","playerID")
        name=pick(obj,"name","playerName","fullName")
        if not pid and not name:
            continue
        value=player_estimated_value(obj)
        if value is None:
            continue
        if name:
            out[norm_team_name(name)]={"id":pid,"value":value}
        if pid:
            out[str(pid)]={"id":pid,"value":value}
    return out


def enrich_lineup_values(players, team_payload_data):
    """Attach FotMob ETV to the confirmed starting XI and sum it."""
    if not players:
        return None
    fmap=squad_value_map(team_payload_data)
    total=0.0
    found=0
    for p in players:
        pid=p.get("playerId") or p.get("id")
        rec=fmap.get(str(pid)) if pid else None
        if rec is None:
            rec=fmap.get(norm_team_name(p.get("name")))
        if rec is None and pid:
            pd=player_payload(pid)
            val=player_estimated_value(pd)
            if val is not None:
                rec={"id":pid,"value":val}
        if rec and rec.get("value") is not None:
            p["estimatedValue"]=round(float(rec["value"]))
            total += float(rec["value"])
            found += 1
    return round(total) if found else None

def league_payload(league_id, name=""):
    key=str(league_id)
    if not league_id: return {}
    if key not in LEAGUE_CACHE:
        try: LEAGUE_CACHE[key]=get(f"{ROOT}/api/data/leagues",{"id":key})
        except Exception:
            try: LEAGUE_CACHE[key]=get(f"{ROOT}/api/leagues",{"id":key})
            except Exception:
                LEAGUE_CACHE[key]={}
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




def _find_team_league(payload):
    """Extract a team's primary/current domestic league from a FotMob payload.
    Works with both legacy and current /api/data/teams shapes.
    """
    candidates=[]
    for obj in walk(payload):
        if not isinstance(obj,dict):
            continue
        lid=pick(obj,"leagueId","parentLeagueId","primaryLeagueId")
        name=pick(obj,"leagueName","league", "name")
        ccode=pick(obj,"ccode","countryCode","countryCode3")
        if isinstance(name,dict):
            lid=lid or pick(name,"id","leagueId")
            ccode=ccode or pick(name,"ccode","countryCode")
            name=pick(name,"name","leagueName")
        if not lid or not name or str(name).lower() in ("international","unknown"):
            continue
        n=str(name).lower()
        # Prefer domestic league-like competitions; exclude obvious cups/UEFA.
        cup=any(k in n for k in ("cup","copa","pokal","champions","europa","conference","super cup","qualification"))
        score=0 if cup else 10
        if "league" in n or n in {"premier league","laliga","bundesliga","serie a","ligue 1","eredivisie","primeira liga"}:
            score += 5
        candidates.append((score, {"division":str(name),"leagueId":lid,"ccode":ccode}))
    if not candidates:
        return {"division":None,"leagueId":None,"ccode":None}
    candidates.sort(key=lambda x:x[0], reverse=True)
    return candidates[0][1]


def current_league(payload):
    explicit=_find_team_league(payload)
    if explicit.get("division"):
        base, display, country = normalize_comp(explicit.get("division"), explicit.get("ccode"), explicit.get("country"))
        explicit["division"] = display
        explicit["baseDivision"] = base
        explicit["country"] = country
        return explicit
    for obj in walk(payload):
        if not isinstance(obj,dict): continue
        name=pick(obj,"leagueName"); lid=pick(obj,"leagueId")
        if name and lid:
            n=str(name).lower()
            if not any(k in n for k in ("cup","champions","europa","conference","pokal","copa")):
                ccode=pick(obj,"ccode","countryCode")
                base,display,country=normalize_comp(str(name),ccode,pick(obj,"country","countryName"))
                return {"division":display,"baseDivision":base,"leagueId":lid,"ccode":ccode,"country":country}
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
            payload = get(f"{ROOT}/api/data/leagues", {"id": str(league_id), "season": season})
            pos = table_position(payload, team_id)
            if pos is not None:
                return pos
        except Exception as exc:
            print("Historical league lookup failed", league_id, season, exc)
    return None

RECENT_DAILY_CACHE={}

def daily_matches_for_date(day):
    key=day.strftime("%Y%m%d")
    if key not in RECENT_DAILY_CACHE:
        try: RECENT_DAILY_CACHE[key]=match_rows(daily(day))
        except Exception as exc:
            print(f"RECENT {key} failed: {exc}")
            RECENT_DAILY_CACHE[key]=[]
    return RECENT_DAILY_CACHE[key]

def form_from_recent_daily(team_id,before_date,days_back=35):
    rows=[]; seen=set()
    for n in range(1,days_back+1):
        for m in daily_matches_for_date(before_date-dt.timedelta(days=n)):
            if status(m)!="FT": continue
            h=m.get("home") or {}; a=m.get("away") or {}
            hid,aid=pick(h,"id","teamId"),pick(a,"id","teamId")
            if str(team_id) not in (str(hid),str(aid)): continue
            hs,aa=score(m)
            if hs is None or aa is None: continue
            comp=str(m.get("_league_name") or "").lower()
            if any(x in comp for x in ("cup","champions","europa","conference","pokal","libertadores","sudamericana")): continue
            mid=str(m.get("id"))
            if mid in seen: continue
            seen.add(mid)
            if str(team_id)==str(hid): gf,ga=int(hs),int(aa); opp=pick(a,"name","longName") or "Opponent"
            else: gf,ga=int(aa),int(hs); opp=pick(h,"name","longName") or "Opponent"
            rows.append({"date":(m.get("status") or {}).get("utcTime") or m.get("utcTime"),
                         "result":"W" if gf>ga else "D" if gf==ga else "L","gf":gf,"ga":ga,"opponent":opp,
                         "competition":m.get("_league_name")})
    rows.sort(key=lambda x:x.get("date") or "",reverse=True)
    return rows[:5]


def prefetch_recent_history(anchor, days_back=21):
    days=[anchor-dt.timedelta(days=n) for n in range(1,days_back+1)]
    def one(day): daily_matches_for_date(day)
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(one,days))
    print(f"RECENT HISTORY: {sum(bool(v) for v in RECENT_DAILY_CACHE.values())}/{len(days)} daily feeds loaded",flush=True)

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


def previous_finish(payload, team_id, league_id=None):
    """
    Return the team's FINAL position from the completed 2025/26 league table.

    Do not read a 'position' field from the current team payload: FotMob team
    payloads can contain current-season standings nested alongside historical
    season metadata, which caused current ranks to be mislabeled as last-season
    finishes.
    """
    if league_id and team_id:
        try:
            pos = historical_position(league_id, team_id)
            if pos is not None:
                return int(pos)
        except Exception as exc:
            print("Historical table lookup failed", league_id, team_id, exc)

    # Known 2025/26 Premier League correction for the current project's
    # highest-visibility cases. This is only a fallback if the historical
    # league endpoint is unavailable.
    name = ""
    for obj in walk(payload):
        if isinstance(obj, dict):
            n = pick(obj, "name", "teamName", "longName")
            if n:
                name = str(n).strip().lower()
                break

    premier_league_fallback = {
        "arsenal": 1,
        "manchester city": 2,
        "man city": 2,
        "manchester united": 3,
        "man united": 3,
        "aston villa": 4,
        "liverpool": 5,
        "bournemouth": 6,
        "afc bournemouth": 6,
        "sunderland": 7,
        "brighton": 8,
        "brighton & hove albion": 8,
        "crystal palace": 15,
        "palace": 15,
        "chelsea": 9,
        "newcastle": 10,
        "newcastle united": 10,
        "nottingham forest": 11,
        "nott'm forest": 11,
        "everton": 12,
        "brentford": 13,
        "fulham": 14,
        "tottenham": 17,
        "tottenham hotspur": 17,
        "west ham": 18,
        "west ham united": 18,
        "burnley": 19,
        "wolverhampton wanderers": 20,
        "wolves": 20,
    }
    return premier_league_fallback.get(name)


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
    result = {str(home_id): [], str(away_id): []}
    content=detail.get("content") if isinstance(detail,dict) else None
    lb=content.get("lineup") if isinstance(content,dict) else None
    if isinstance(lb,dict):
        for side,tid in (("homeTeam",home_id),("awayTeam",away_id)):
            block=lb.get(side) or {}
            for row in (block.get("starters") or block.get("players") or []):
                if not isinstance(row,dict): continue
                pl=row.get("player") if isinstance(row.get("player"),dict) else row
                name=pick(pl,"name","playerName")
                if name:
                    st=row.get("stats") if isinstance(row.get("stats"),dict) else row.get("statistics") if isinstance(row.get("statistics"),dict) else {}
                    result[str(tid)].append({"name":name,"playerId":pick(pl,"id","playerId") or pick(row,"playerId","playerID"),
                        "image":(f"https://images.fotmob.com/image_resources/playerimages/{(pick(pl,"id","playerId") or pick(row,"playerId","playerID"))}.png" if (pick(pl,"id","playerId") or pick(row,"playerId","playerID")) else None),"position":pick(row,"position","role","positionName") or pick(pl,"position"),
                        "rating":pick(st,"rating","FotMob rating") or pick(row,"rating","matchRating"),"starter":True})
    for obj in walk(detail):
        if not isinstance(obj, dict): continue
        lines=obj.get("lineups")
        if not isinstance(lines,list): continue
        for team in lines:
            if not isinstance(team,dict): continue
            tid=pick(team,"teamId","id")
            if tid is None or str(tid) not in result: continue
            players=team.get("players") or []
            for player in players:
                if not isinstance(player,dict): continue
                p=player.get("player") if isinstance(player.get("player"),dict) else player
                name=pick(p,"name","playerName")
                if not name: continue
                stats=player.get("statistics") if isinstance(player.get("statistics"),dict) else {}
                result[str(tid)].append({"name":name,"playerId":pick(p,"id","playerId") or pick(player,"playerId","playerID"),"position":pick(player,"position","role","positionName") or pick(p,"position","role"),"rating":pick(stats,"rating") or pick(player,"rating","matchRating") or pick(p,"rating","matchRating"),"starter":player.get("starter",not player.get("substitute",False))})
    for key in result:
        seen=set(); clean=[]
        for p in result[key]:
            if p["name"] in seen: continue
            seen.add(p["name"]); clean.append(p)
        result[key]=clean[:18]
    return result[str(home_id)],result[str(away_id)]


def xg(detail):
    for obj in walk(detail):
        if not isinstance(obj, dict):
            continue
        if str(obj.get("title", "")).lower() in {"expected goals (xg)", "expected goals", "xg"}:
            values = obj.get("stats")
            if isinstance(values, list) and len(values) >= 2:
                try: return float(values[0]), float(values[1])
                except (TypeError, ValueError): pass
    return None, None


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
    p = [math.exp(-lam)]
    for k in range(1, max_goals + 1):
        p.append(p[-1] * lam / k)
    return p


def league_strength(name):
    base = str(name or "").strip()
    exact = {
        "England Premier League":1885, "Scotland Premiership":1600,
        "England Championship":1660, "England League One":1410,
        "England League Two":1270, "Scotland Championship":1450,
        "Scotland League One":1320, "Scotland League Two":1250,
        "Germany Bundesliga":1765, "Austria Bundesliga":1610,
        "Italy Serie A":1855, "Ecuador Serie A":1545,
    }
    if base in exact:
        return exact[base]
    return STRENGTH.get(base, 1500)


def _form_points(form):
    return sum(3 if c == "W" else 1 if c == "D" else 0 for c in str(form or "")[-5:])


def _recent_stats(payload, team_id):
    rows=[]
    for obj in walk(payload):
        if not isinstance(obj,dict): continue
        h=obj.get("home") or obj.get("homeTeam"); a=obj.get("away") or obj.get("awayTeam")
        if not isinstance(h,dict) or not isinstance(a,dict): continue
        hs,ass=pick(h,"score","goals"),pick(a,"score","goals")
        hid,aid=pick(h,"id","teamId"),pick(a,"id","teamId")
        if hs is None or ass is None or hid is None or aid is None: continue
        try: hs,ass=int(hs),int(ass)
        except: continue
        if str(team_id)==str(hid):
            opp=pick(a,"name","longName") or "Opponent"; gf,ga=hs,ass; result="W" if hs>ass else "D" if hs==ass else "L"
        elif str(team_id)==str(aid):
            opp=pick(h,"name","longName") or "Opponent"; gf,ga=ass,hs; result="W" if ass>hs else "D" if hs==ass else "L"
        else: continue
        rows.append({"result":result,"gf":gf,"ga":ga,"opponent":opp})
    return rows[-5:]


def _team_xg(payload, team_id):
    vals=[]
    for obj in walk(payload):
        if not isinstance(obj,dict): continue
        tid=obj.get("teamId") or obj.get("id")
        if tid is not None and str(tid)!=str(team_id): continue
        for key in ("xg","expectedGoals","expectedGoalsFor","xGFor"):
            v=as_num(obj.get(key))
            if v is not None and 0<=v<=6: vals.append(v)
        stats=obj.get("stats")
        if isinstance(stats,dict):
            for key in ("xg","expectedGoals","expectedGoalsFor"):
                v=as_num(stats.get(key))
                if v is not None and 0<=v<=6: vals.append(v)
    return round(sum(vals[-5:])/len(vals[-5:]),2) if vals else None


def _rating_prior(payload, team_id):
    vals=[]
    for obj in walk(payload):
        if not isinstance(obj,dict): continue
        for key in ("averageRating","seasonRating","rating"):
            v=as_num(obj.get(key))
            if v is not None and 5<=v<=10: vals.append(v)
    return round(sum(vals[-20:])/len(vals[-20:]),2) if vals else None


def _strength(team):
    # 0 is neutral. Division is the structural prior; recent form and season finish
    # are bounded so one hot/cold run cannot overwhelm the league gap.
    div=league_strength(team.get("division"))
    same_season_pos=team.get("position")
    last=team.get("lastSeasonPosition")
    form=_form_points(team.get("form"))
    gf=team.get("recentGF",0); ga=team.get("recentGA",0)
    rating=team.get("ratingPrior")
    s=float(div)
    if same_season_pos: s += max(-35,min(35,(12-float(same_season_pos))*3.0))
    if last: s += max(-55,min(55,(12-float(last))*3.8))
    s += max(-42,min(42,(form-7)*5.0))
    s += max(-24,min(24,(float(gf)-float(ga))*2.5))
    if rating is not None: s += max(-20,min(20,(rating-7.0)*35))
    # Starting-XI estimated transfer value is a secondary quality signal.
    # Use log scale so €150m vs €300m matters, but never dominates form/table.
    xi_value=as_num(team.get("lineupEstimatedValue"))
    if xi_value and xi_value > 0:
        s += max(-28,min(28,math.log10(xi_value/100000000.0)*24))
    return s


def _dc_adjust(i,j,rho=-0.10):
    # Dixon-Coles low-score correction; keeps draws realistic without forcing them.
    if i==0 and j==0: return 1-rho
    if i==0 and j==1: return 1+rho
    if i==1 and j==0: return 1+rho
    if i==1 and j==1: return 1-rho
    return 1.0


def model(match):
    h,a=match["homeData"],match["awayData"]
    same=bool(h.get("division") and h.get("division")==a.get("division"))
    hs,as_=_strength(h),_strength(a)
    # Current position is only comparable within the same division.
    raw_gap=hs-as_
    factors=[]
    factors.append(["Division / team strength",round((league_strength(h.get("division"))-league_strength(a.get("division")))/10,1)])
    if same and h.get("position") and a.get("position"):
        factors.append(["Current table",round((a["position"]-h["position"])*2.0,1)])
    else: factors.append(["Current table",0.0])
    factors.append(["Last-season prior",round(((a.get("lastSeasonPosition") or 12)-(h.get("lastSeasonPosition") or 12))*1.6,1)])
    factors.append(["Recent form",round((_form_points(h.get("form"))-_form_points(a.get("form")))*2.5,1)])
    factors.append(["Recent goal difference",round(((h.get("recentGF",0)-h.get("recentGA",0))-(a.get("recentGF",0)-a.get("recentGA",0)))*1.5,1)])
    factors.append(["Squad / transfer",round((h.get("transferImpact") or 0)-(a.get("transferImpact") or 0),1)])
    factors.append(["Starting XI quality",round(((h.get("xiRating") or h.get("ratingPrior") or 7)-(a.get("xiRating") or a.get("ratingPrior") or 7))*18,1)])
    hv=as_num(h.get("lineupEstimatedValue")); av=as_num(a.get("lineupEstimatedValue"))
    if hv and av and hv>0 and av>0:
        factors.append(["XI estimated value",round(max(-30,min(30,math.log(hv/av)*10)),1)])
    factors.append(["Home advantage",24 if same else 12])
    # xG is used only as a secondary goal signal, never as a post-match leak for upcoming games.
    xh,xa=h.get("xg"),a.get("xg")
    # Rating gap is converted into expected goals with a deliberately shallow slope.
    home_adv=0.18 if same else 0.08
    goal_gap=max(-1.55,min(1.55,raw_gap/520.0))
    league_total=2.62
    comp=str(match.get("competition") or "")
    if any(k in comp for k in ("Serie A","Ligue 1")): league_total=2.50
    if any(k in comp for k in ("Bundesliga","Eredivisie","Premier League")): league_total=2.72
    if "Champions League" in comp: league_total=2.78
    if "Cup" in comp or "Copa" in comp or "Pokal" in comp: league_total=2.68
    lam_h=max(.28,min(3.9,league_total/2 + home_adv + goal_gap/2))
    lam_a=max(.24,min(3.6,league_total/2 - goal_gap/2))
    if xh is not None and xa is not None:
        # Team/season xG gets only 20% weight because early-season samples can be thin.
        lam_h=.80*lam_h+.20*max(.20,min(3.6,float(xh)))
        lam_a=.80*lam_a+.20*max(.20,min(3.4,float(xa)))
    # Confirmed XI quality should nudge goals, not turn a match into a 5-point certainty.
    if h.get("xiRating") is not None and a.get("xiRating") is not None:
        q=max(-.28,min(.28,(h["xiRating"]-a["xiRating"])*.10)); lam_h=max(.25,min(4.0,lam_h+q)); lam_a=max(.22,min(3.6,lam_a-q*.55))
    grid=[]; pH=pD=pA=0.0
    ph=poisson(lam_h,9); pa=poisson(lam_a,9)
    for i,pi in enumerate(ph):
        for j,pj in enumerate(pa):
            q=pi*pj*_dc_adjust(i,j)
            grid.append((q,i,j))
            if i>j:pH+=q
            elif i==j:pD+=q
            else:pA+=q
    # ---------------------------------------------------------------
    # Draw calibration: empirical league + team draw tendency.
    #
    # The old calibration only looked at mathematical closeness. That can
    # still produce a whole matchday with zero DRAW verdicts because the
    # underlying Poisson side probabilities remain slightly larger.
    #
    # Here we use real completed fixtures already fetched by
    # prefetch_recent_history(), without looking at the future result.
    # It is a calibration prior, not a forced draw.
    # ---------------------------------------------------------------
    def _result_draw_rate(rows):
        vals=[1 if str(r.get("result"))=="D" else 0 for r in (rows or [])]
        return (sum(vals)/len(vals)) if vals else None

    def _team_draw_rate(team):
        rows=team.get("recentResults") or []
        vals=[1 if str(r.get("result"))=="D" else 0 for r in rows]
        return (sum(vals)/len(vals)) if vals else None

    def _league_recent_draw_rate(competition, country):
        wanted=str(competition or "").strip().lower()
        ctry=str(country or "").strip().lower()
        vals=[]
        for rows in RECENT_DAILY_CACHE.values():
            for rm in rows or []:
                if status(rm)!="FT": continue
                rcomp=str(rm.get("_league_name") or "").strip().lower()
                rcountry=str(rm.get("_country") or "").strip().lower()
                # Prefer exact competition identity; country is a secondary
                # guard so generic "Bundesliga" cannot mix Germany/Austria.
                if wanted and rcomp != wanted: continue
                if ctry and rcountry and rcountry != ctry: continue
                hs,aa=score(rm)
                if hs is None or aa is None: continue
                vals.append(1 if int(hs)==int(aa) else 0)
        return (sum(vals)/len(vals)) if vals else None

    league_draw=_league_recent_draw_rate(
        match.get("competitionName") or match.get("competition"),
        match.get("competitionCountry")
    )
    home_draw=_team_draw_rate(h)
    away_draw=_team_draw_rate(a)

    observed=[x for x in (league_draw,home_draw,away_draw) if x is not None]
    # Global football baseline is only a fallback. Real league/team data gets
    # most of the weight whenever available.
    empirical_draw=(0.30 if not observed else
                    (0.50*(league_draw if league_draw is not None else 0.30) +
                     0.25*(home_draw if home_draw is not None else (league_draw if league_draw is not None else 0.30)) +
                     0.25*(away_draw if away_draw is not None else (league_draw if league_draw is not None else 0.30))))

    # Keep the empirical prior in a realistic range. This prevents a tiny
    # 5-game team sample from turning into a 60% draw prior.
    empirical_draw=max(0.18,min(0.36,empirical_draw))

    strength_close=max(0.0,1.0-min(1.0,abs(raw_gap)/150.0))
    goal_close=max(0.0,1.0-min(1.0,abs(lam_h-lam_a)/1.45))
    low_total=max(0.0,min(1.0,(3.30-(lam_h+lam_a))/1.60))

    # Team draw tendencies matter most when the teams are otherwise close.
    tendency=(0.55*max(0.0,min(1.0,(empirical_draw-0.18)/0.18))
              +0.45*max(0.0,min(1.0,(strength_close+goal_close)/2.0)))

    # Convert real observed draw frequency into a target probability. The
    # target remains a probability, never a forced outcome.
    target_draw=max(0.20,min(0.36,
        0.72*empirical_draw +
        0.28*(0.22 + 0.14*strength_close + 0.08*goal_close + 0.04*low_total)
    ))

    raw_total=pH+pD+pA
    raw_draw=pD/raw_total if raw_total else 0.0

    # Blend strongly enough to fix the "zero draws" regression, but only when
    # the match has evidence of being draw-prone. One-sided matches remain
    # dominated by H/A.
    blend=max(0.18,min(0.88,
        0.20 + 0.50*strength_close + 0.20*goal_close + 0.10*tendency
    ))

    calibrated_draw=raw_draw*(1-blend)+target_draw*blend
    if raw_total>0 and calibrated_draw>raw_draw:
        extra=(calibrated_draw-raw_draw)*raw_total
        side=pH+pA
        if side>0:
            pH-=extra*(pH/side)
            pA-=extra*(pA/side)
            pD+=extra

    z=pH+pD+pA
    probs=[pH/z,pD/z,pA/z]

    # A draw verdict is allowed when DRAW is the most likely calibrated
    # outcome. There is deliberately no "every N games force X" mechanism.
    idx=max(range(3),key=lambda k:probs[k])
    verdict=match["home"] if idx==0 else "DRAW" if idx==1 else match["away"]

    allowed=[g for g in grid if
             (idx==0 and g[1]>g[2]) or
             (idx==1 and g[1]==g[2]) or
             (idx==2 and g[1]<g[2])]
    modal=max(allowed or grid,key=lambda x:x[0])
    if league_draw is not None:
        factors.append(["League draw rate",round(league_draw*100,1)])
    if home_draw is not None or away_draw is not None:
        vals=[x for x in (home_draw,away_draw) if x is not None]
        factors.append(["Team draw tendency",round(sum(vals)/len(vals)*100,1)])
    margin=max(probs)-sorted(probs,reverse=True)[1]
    # Confidence is deliberately conservative when evidence is sparse.
    completeness=sum(bool(h.get(k) and a.get(k)) for k in ("division","form","lastSeasonPosition"))
    completeness += 1 if h.get("position") is not None and a.get("position") is not None else 0
    completeness += 1 if h.get("xg") is not None and a.get("xg") is not None else 0
    completeness += 1 if h.get("lineup") and a.get("lineup") else 0
    completeness += 1 if h.get("xiRating") is not None and a.get("xiRating") is not None else 0
    confidence=round(max(43,min(92,47+margin*135+(completeness-4)*1.5)))
    return {"verdict":f"WIN: {verdict}" if verdict!="DRAW" else "DRAW","confidence":confidence,"probabilities":probs,
            "projected":f"{modal[1]}–{modal[2]}","modalScore":f"{modal[1]}–{modal[2]}","expectedGoals":[round(lam_h,2),round(lam_a,2)],
            "factors":factors,"dataCompleteness":round(completeness/8*100),
            "decisionNote":"Division strength + opponent-aware form + last-season prior + squad/XI evidence + restrained home advantage + evidence-based draw calibration"}



def safe_call(label, fn, default=None):
    try:
        return fn()
    except Exception as exc:
        print(f"{label} failed: {exc}")
        return default


def enrich_base(m, now):
    home,away=m.get("home") or {},m.get("away") or {}
    hn,an=pick(home,"name","longName"),pick(away,"name","longName")
    hp=TEAM_CACHE.get(str(home.get("id"))) or safe_call(f"Team {hn}",lambda:team_payload(home.get("id"),home.get("name") or home.get("longName")),{})
    ap=TEAM_CACHE.get(str(away.get("id"))) or safe_call(f"Team {an}",lambda:team_payload(away.get("id"),away.get("name") or away.get("longName")),{})
    hl,al=current_league(hp),current_league(ap)
    # Fixture competition is a safe display fallback, but only use it as the
    # team's division when it looks like a domestic league (not a cup/UEFA tie).
    fixture_div=str(m.get("_league_name") or "")
    if not hl.get("division") and fixture_div and not any(k in fixture_div.lower() for k in ("cup","copa","pokal","champions","europa","conference","qualification")):
        _b,_d,_c=normalize_comp(fixture_div,m.get("_ccode"),m.get("_country"))
        hl={"division":_d,"baseDivision":_b,"leagueId":m.get("_league_id"),"ccode":m.get("_ccode"),"country":_c}
    if not al.get("division") and fixture_div and not any(k in fixture_div.lower() for k in ("cup","copa","pokal","champions","europa","conference","qualification")):
        _b,_d,_c=normalize_comp(fixture_div,m.get("_ccode"),m.get("_country"))
        al={"division":_d,"baseDivision":_b,"leagueId":m.get("_league_id"),"ccode":m.get("_ccode"),"country":_c}
    hleague=LEAGUE_CACHE.get(str(hl.get("leagueId"))) or (safe_call(f"League {hl.get('leagueId')}",lambda:league_payload(hl.get("leagueId"),hl.get("division")),{}) if hl.get("leagueId") else {})
    aleague=LEAGUE_CACHE.get(str(al.get("leagueId"))) or (safe_call(f"League {al.get('leagueId')}",lambda:league_payload(al.get("leagueId"),al.get("division")),{}) if al.get("leagueId") else {})
    hpos=table_position(hleague,home.get("id")) or table_position(hp,home.get("id")); apos=table_position(aleague,away.get("id")) or table_position(ap,away.get("id"))
    hlast=previous_finish(hp,home.get("id"),hl.get("leagueId")); alast=previous_finish(ap,away.get("id"),al.get("leagueId"))
    h_recent=form_from_recent_daily(home.get("id"),now.date())
    a_recent=form_from_recent_daily(away.get("id"),now.date())
    h_form="".join(x["result"] for x in h_recent) or form_from_team(hp,home.get("id"))
    a_form="".join(x["result"] for x in a_recent) or form_from_team(ap,away.get("id"))
    hd={"id":home.get("id"),"division":hl.get("division"),"leagueId":hl.get("leagueId"),"ccode":hl.get("ccode"),"position":hpos,"form":h_form,"lastSeasonPosition":hlast,"lastSeason":"2025/26","transferImpact":transfer_impact(hp),"squadEstimatedValue":None,"lineupEstimatedValue":None,"lineup":[],"injuries":[]}
    ad={"id":away.get("id"),"division":al.get("division"),"leagueId":al.get("leagueId"),"ccode":al.get("ccode"),"position":apos,"form":a_form,"lastSeasonPosition":alast,"lastSeason":"2025/26","transferImpact":transfer_impact(ap),"squadEstimatedValue":None,"lineupEstimatedValue":None,"lineup":[],"injuries":[]}
    hr=h_recent or _recent_stats(hp,home.get("id")); ar=a_recent or _recent_stats(ap,away.get("id"))
    for d,rows,payload,tid in ((hd,hr,hp,home.get("id")),(ad,ar,ap,away.get("id"))):
        d["formPoints"]=_form_points(d["form"]); d["recentResults"]=rows; d["recentGF"]=sum(x["gf"] for x in rows); d["recentGA"]=sum(x["ga"] for x in rows); d["ratingPrior"]=_rating_prior(payload,tid); d["xgSeason"]=_team_xg(payload,tid)
    return hp,ap,hd,ad


def fotmob_incidents(detail, home_id=None, away_id=None):
    """Best-effort goal extraction from FotMob match detail/liveticker payload."""
    if not isinstance(detail,dict): return []
    out=[]
    content=detail.get("content") if isinstance(detail.get("content"),dict) else {}
    lt=content.get("liveticker") if isinstance(content.get("liveticker"),dict) else {}
    # Common shape: liveticker -> events / teams; also walk arbitrary nested event lists.
    candidates=[]
    for obj in walk(lt):
        if isinstance(obj,dict):
            typ=str(pick(obj,"type","eventType","incidentType","action") or "").lower()
            if "goal" in typ or obj.get("isGoal") is True:
                candidates.append(obj)
    seen=set()
    for e in candidates:
        player=e.get("player") if isinstance(e.get("player"),dict) else {}
        scorer=pick(player,"name","fullName") or pick(e,"playerName","scorer","name")
        if not scorer: continue
        minute=pick(e,"time","minute","minuteString")
        assist=e.get("assist") if isinstance(e.get("assist"),dict) else {}
        assist_name=pick(assist,"name","fullName") or pick(e,"assistName","assistPlayer")
        key=(str(scorer),str(minute),str(assist_name))
        if key in seen: continue
        seen.add(key)
        is_home=None
        tid=pick(e,"teamId","teamID")
        if home_id is not None and str(tid)==str(home_id): is_home=True
        elif away_id is not None and str(tid)==str(away_id): is_home=False
        scorer_id=pick(player,"id","playerId") or pick(e,"playerId","playerID")
        assist_id=pick(assist,"id","playerId") or pick(e,"assistPlayerId","assistPlayerID")
        out.append({"minute":minute,
                    "team":"home" if is_home is True else "away" if is_home is False else None,
                    "scorer":scorer,"scorerId":scorer_id,
                    "scorerImage":f"https://images.fotmob.com/image_resources/playerimages/{scorer_id}.png" if scorer_id else None,
                    "assist":assist_name,"assistId":assist_id,
                    "assistImage":f"https://images.fotmob.com/image_resources/playerimages/{assist_id}.png" if assist_id else None,
                    "ownGoal":bool(e.get("ownGoal") or e.get("isOwnGoal"))})
    return sorted(out,key=lambda x:(str(x.get("minute") or ""),x.get("scorer") or ""))

def apply_match_detail(detail,hd,ad):
    if not detail:return "Not available from FotMob."
    fh,fa=lineup(detail,hd["id"],ad["id"])
    if fh and fa:
        hd["lineup"],ad["lineup"]=fh,fa
        hd["xiRating"]=lineup_quality({"players":fh}); ad["xiRating"]=lineup_quality({"players":fa})
        hd["lineupEstimatedValue"]=enrich_lineup_values(hd["lineup"], TEAM_CACHE.get(str(hd["id"]), {}))
        ad["lineupEstimatedValue"]=enrich_lineup_values(ad["lineup"], TEAM_CACHE.get(str(ad["id"]), {}))
    xh,xa=xg(detail)
    # Only use match xG after kickoff; before kickoff it is not a valid predictor.
    if xh is not None and xa is not None:
        hd["matchXG"],ad["matchXG"]=xh,xa
    return h2h(detail)


def sofa_for_match(m, hn, an, now):
    """Fetch lineup + incidents independently; one failure never blocks the match."""
    day_key = (m.get("utcTime") or "")[:10] or now.date().isoformat()
    evmap = SOFA_EVENTS.get(day_key)
    if evmap is None:
        try:
            evmap = sofa_event_map(sofa_scheduled(dt.date.fromisoformat(day_key)))
        except Exception as exc:
            print("Sofascore schedule failed", day_key, exc)
            evmap = {}
        SOFA_EVENTS[day_key] = evmap
    event = evmap.get((norm_team_name(hn), norm_team_name(an)))
    if not event:
        return None, {}, {}, []
    sid = event.get("id")
    lh = la = {}
    incidents = []
    # Don't waste lineup calls on old/completed games unless the lineup is missing from FotMob; caller decides.
    try:
        lh, la = sofa_lineups(sid)
    except Exception as exc:
        print("Sofascore lineup failed", sid, exc)
    try:
        incidents = sofa_incidents(sid)
    except Exception as exc:
        print("Sofascore incidents failed", sid, exc)
    return event, lh, la, incidents


def detail_for_match(mid):
    return safe_call(f"Detail {mid}", lambda: match_details(mid), {})


def apply_sofa(hd, ad, event, lh, la):
    if not event:
        return
    if lh.get("players") and la.get("players"):
        hd["lineup"] = lh["players"]; ad["lineup"] = la["players"]
        hd["bench"] = lh.get("substitutes", []); ad["bench"] = la.get("substitutes", [])
        hd["missingPlayers"] = lh.get("missingPlayers", []); ad["missingPlayers"] = la.get("missingPlayers", [])
        hd["formation"] = lh.get("formation"); ad["formation"] = la.get("formation")
        hd["lineupConfirmed"] = lh.get("confirmed", False); ad["lineupConfirmed"] = la.get("confirmed", False)
        hd["xiRating"] = lineup_quality(lh); ad["xiRating"] = lineup_quality(la)
        hd["lineupEstimatedValue"]=enrich_lineup_values(hd.get("lineup",[]), TEAM_CACHE.get(str(hd["id"]), {}))
        ad["lineupEstimatedValue"]=enrich_lineup_values(ad.get("lineup",[]), TEAM_CACHE.get(str(ad["id"]), {}))


def build_match(m, now, sofa_info):
    mid=pick(m,"id"); home,away=m.get("home") or {},m.get("away") or {}; hn,an=pick(home,"name","longName"),pick(away,"name","longName")
    hp,ap,hd,ad=enrich_base(m,now)
    detail=detail_for_match(mid)
    h2h_summary=apply_match_detail(detail,hd,ad) if detail else "Not available from FotMob."
    sofa_event,sofa_lh,sofa_la,incidents=sofa_info
    if not incidents and detail:
        incidents=fotmob_incidents(detail,hd.get("id"),ad.get("id"))
    apply_sofa(hd,ad,sofa_event,sofa_lh,sofa_la)
    # Prefer SofaScore lineup if available, otherwise keep FotMob detail lineup.
    if not hd.get("lineup") and not ad.get("lineup") and detail:
        fh,fa=lineup(detail,hd["id"],ad["id"])
        if fh and fa:
            hd["lineup"],ad["lineup"]=fh,fa
            hd["lineupEstimatedValue"]=enrich_lineup_values(hd["lineup"], TEAM_CACHE.get(str(hd["id"]), {}))
            ad["lineupEstimatedValue"]=enrich_lineup_values(ad["lineup"], TEAM_CACHE.get(str(ad["id"]), {}))
    hs,ass=score(m); st=m.get("status") or {}
    status_value=status(m)
    out={"id":str(mid),"competition":m.get("_display_competition") or m.get("_league_name") or "Competition","competitionName":m.get("_league_name") or "Competition","competitionCountry":m.get("_country") or "Unknown","competitionCode":str(m.get("_ccode") or "INT").upper(),"competitionFlag":flag(m.get("_ccode"),m.get("_country")),"home":hn,"away":an,"homeScore":hs,"awayScore":ass,"status":status_value,"kickoff":st.get("utcTime") or m.get("utcTime"),"minute":{"short":pick(st,"reason","period") or ""},"homeData":hd,"awayData":ad,"h2hSummary":h2h_summary,"scorers":incidents,"sofascoreEventId":sofa_event.get("id") if sofa_event else None,"lineupSource":"Sofascore" if sofa_lh.get("players") and sofa_la.get("players") else ("FotMob" if hd.get("lineup") and ad.get("lineup") else None),"fotmobMatchUrl":f"{ROOT}/matches/{mid}/match-details"}
    # For upcoming games, season/team xG is the predictive xG input; post-match xG remains informational.
    if status_value in ("LIVE","FT") and hd.get("matchXG") is not None:
        hd["xg"],ad["xg"]=hd.get("matchXG"),ad.get("matchXG")
    else:
        hd["xg"],ad["xg"]=hd.get("xgSeason"),ad.get("xgSeason")
    out["model"]=model(out)
    return out


def _prep_team_cache(rows):
    ids={str((m.get("home") or {}).get("id")) for m in rows}|{str((m.get("away") or {}).get("id")) for m in rows}
    ids.discard("None")
    name_by_id={}
    for m in rows:
        for side in ("home","away"):
            t=m.get(side) or {}
            if t.get("id") is not None:
                name_by_id[str(t["id"])] = pick(t,"name","longName") or ""
    def one(tid):
        try: TEAM_CACHE[tid]=team_payload(tid,name_by_id.get(tid,""))
        except Exception as exc: print("TEAM",tid,"failed",exc)
    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(one,ids))
    league_ids=set()
    for tid,p in TEAM_CACHE.items():
        if not isinstance(p,dict):continue
        lg=current_league(p).get("leagueId")
        if lg: league_ids.add(str(lg))
    league_name_by_id={}
    for p in TEAM_CACHE.values():
        if isinstance(p,dict):
            lg=current_league(p)
            if lg.get("leagueId"): league_name_by_id[str(lg["leagueId"])]=lg.get("division") or ""
    def one_lid(lid):
        try: LEAGUE_CACHE[lid]=league_payload(lid,league_name_by_id.get(lid,""))
        except Exception as exc: print("LEAGUE",lid,"failed",exc)
    with ThreadPoolExecutor(max_workers=8) as ex:list(ex.map(one_lid,league_ids))


def _sofa_map_for_rows(rows,now):
    # FotMob UTC dates can straddle SofaScore's scheduled-events date boundary.
    base_dates=sorted({(m.get("status") or {}).get("utcTime",m.get("utcTime", ""))[:10] for m in rows if m.get("utcTime")})
    dates=set()
    for ds in base_dates:
        try:
            d=dt.date.fromisoformat(ds)
            for delta in (-1,0,1): dates.add((d+dt.timedelta(days=delta)).isoformat())
        except Exception: pass
    for day in sorted(dates):
        try: SOFA_EVENTS[day]=sofa_scheduled(dt.date.fromisoformat(day))
        except Exception as exc: print("Sofascore schedule",day,"failed",exc);SOFA_EVENTS[day]=[]
    out={}
    for m in rows:
        day=((m.get("status") or {}).get("utcTime") or m.get("utcTime") or "")[:10]
        hn=pick(m.get("home") or {},"name","longName"); an=pick(m.get("away") or {},"name","longName")
        ev=None
        for d in (day,):
            ev=sofa_find_event(SOFA_EVENTS.get(d,[]),hn,an)
            if ev: break
        if not ev:
            # Try adjacent UTC dates for midnight/timezone crossover.
            try:
                base=dt.date.fromisoformat(day)
                for delta in (-1,1):
                    ev=sofa_find_event(SOFA_EVENTS.get((base+dt.timedelta(days=delta)).isoformat(),[]),hn,an)
                    if ev: break
            except Exception: pass
        if not ev:
            out[str(m.get("id"))]=(None,{}, {}, []); continue
        sid=ev.get("id"); need_lineup=status(m) in ("LIVE","UPCOMING")
        lh=la={};inc=[]
        try:
            if need_lineup: lh,la=sofa_lineups(sid)
        except Exception as exc: print("LINEUP",sid,"failed",exc)
        try:
            if status(m) in ("LIVE","FT"): inc=sofa_incidents(sid)
        except Exception as exc: print("INCIDENT",sid,"failed",exc)
        out[str(m.get("id"))]=(ev,lh,la,inc)
    return out


def main():
    now=dt.datetime.now(dt.timezone.utc).astimezone(TZ); days=[now.date(),now.date()+dt.timedelta(days=1)]; raw=[]; errors=[]
    for day in days:
        try:
            payload=daily(day); rows=match_rows(payload); print(f"FotMob {day}: {len(rows)} raw fixtures",flush=True); raw.extend(rows)
        except Exception as exc: errors.append(f"{day}: {exc}")
    if not raw: raise RuntimeError("No FotMob fixtures returned; refusing to overwrite existing data")
    # Normalize competition identity so Kuwait Premier League can never masquerade as England Premier League.
    for m in raw:
        base,display,country=normalize_comp(m.get("_league_name"),m.get("_ccode"),m.get("_country"));m["_display_competition"]=display;m["_country"]=country;m["_base_competition"]=base
    raw=[m for m in raw if (m.get("_base_competition") in SUPPORTED or str(m.get("_league_name","")).startswith("UEFA "))]
    print(f"SUPPORTED FIXTURES: {len(raw)}",flush=True)
    prefetch_recent_history(now.date(),21)
    _prep_team_cache(raw)
    sofa=_sofa_map_for_rows(raw,now)
    results=[None]*len(raw)
    def one(pair):
        i,m=pair
        try:return i,build_match(m,now,sofa.get(str(m.get("id")),(None,{}, {}, [])))
        except Exception as exc:
            print("MATCH",m.get("id"),"failed",exc,flush=True);return i,None
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures=[ex.submit(one,p) for p in enumerate(raw)]
        done=0
        for f in as_completed(futures):
            i,val=f.result();results[i]=val;done+=1
            if done%5==0 or done==len(raw):print(f"PROGRESS {done}/{len(raw)}",flush=True)
    matches=[x for x in results if x]
    matches.sort(key=lambda m:(str(m.get("competition")),m.get("kickoff") or ""))
    payload={"updatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"updated":dt.datetime.now(TZ).strftime("%Y-%m-%d %I:%M:%S %p ET"),"updateMode":"AUTO","refreshIntervalSeconds":300,"fixtureCount":len(matches),"sourceStatus":f"FotMob + Sofascore · {len(matches)} fixtures","sourceErrors":errors,"matches":matches}
    form_n=sum(bool((m.get("homeData") or {}).get("form")) and bool((m.get("awayData") or {}).get("form")) for m in matches)
    div_n=sum(bool((m.get("homeData") or {}).get("division")) and bool((m.get("awayData") or {}).get("division")) for m in matches)
    inc_n=sum(bool(m.get("scorers")) for m in matches)
    lu_n=sum(bool((m.get("homeData") or {}).get("lineup")) and bool((m.get("awayData") or {}).get("lineup")) for m in matches)
    print("ENRICHMENT:",form_n,"form pairs ·",div_n,"divisions ·",inc_n,"incident feeds ·",lu_n,"lineups",flush=True)
    # Do not block the entire feed when secondary enrichment endpoints are
    # temporarily unavailable. The fixture feed itself is authoritative for
    # today's games; enrichment is best-effort and will recover on the next run.
    if form_n == 0 or div_n == 0:
        print("WARNING: secondary enrichment incomplete; publishing fixture feed so the site can stay current", flush=True)
    Path("data").mkdir(exist_ok=True);Path("data/fixtures.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"WROTE {len(matches)} fixtures",flush=True)

if __name__=="__main__":main()
