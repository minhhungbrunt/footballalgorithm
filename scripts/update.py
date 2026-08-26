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


def get(url, params=None, timeout=8, tries=1):
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
            time.sleep(0.5)
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



def sofa_get(path, params=None, timeout=6, tries=1):
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
            time.sleep(.5)
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
            players.append({
                "name":name,
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
        out.append({"minute":i.get("time"),"added":i.get("addedTime"),"team":"home" if i.get("isHome") else "away","scorer":player.get("name"),"assist":assist.get("name"),"ownGoal":bool(i.get("incidentClass")=="ownGoal" or i.get("incidentClass")=="missed")})
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
    key = str(match_id)
    if key not in DETAIL_CACHE:
        DETAIL_CACHE[key] = get(f"{ROOT}/api/matchDetails", {"matchId": key})
    return DETAIL_CACHE[key]


def team_payload(team_id):
    key = str(team_id)
    if key not in TEAM_CACHE:
        TEAM_CACHE[key] = get(f"{ROOT}/api/teams", {"id": key})
    return TEAM_CACHE[key]


def league_payload(league_id):
    key = str(league_id)
    if not league_id:
        return {}
    if key not in LEAGUE_CACHE:
        LEAGUE_CACHE[key] = get(f"{ROOT}/api/leagues", {"id": key})
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
    # Team overview/current table is the source of truth. Never use the cup fixture's competition.
    for obj in walk(payload):
        if not isinstance(obj, dict):
            continue
        season = str(pick(obj, "season", "selectedSeason") or "")
        if season and "2026" not in season:
            continue
        if obj.get("leagueName") and obj.get("leagueId"):
            return {"division": obj["leagueName"], "leagueId": obj["leagueId"], "ccode": obj.get("ccode")}
        data = obj.get("data")
        if isinstance(data, dict) and data.get("leagueName") and data.get("leagueId"):
            return {"division": data["leagueName"], "leagueId": data["leagueId"], "ccode": data.get("ccode")}
    # Fallback: first current table data node.
    for obj in walk(payload):
        if isinstance(obj, dict) and obj.get("leagueName") and obj.get("leagueId"):
            return {"division": obj["leagueName"], "leagueId": obj["leagueId"], "ccode": obj.get("ccode")}
    return {"division": None, "leagueId": None, "ccode": None}


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
            payload = get(f"{ROOT}/api/leagues", {"id": str(league_id), "season": season})
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
    result = {str(home_id): [], str(away_id): []}
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
                result[str(tid)].append({"name":name,"position":pick(player,"position","role","positionName") or pick(p,"position","role"),"rating":pick(stats,"rating") or pick(player,"rating","matchRating") or pick(p,"rating","matchRating"),"starter":player.get("starter",not player.get("substitute",False))})
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
    base = str(name or "")
    if base == "Premier League" or base.endswith(" Premier League"):
        # England gets the real top-flight prior; other countries get a sensible fallback.
        if base == "Premier League" or base == "England Premier League": return 1885
        return 1510
    return STRENGTH.get(base, 1500)


def model(match):
    h, a = match["homeData"], match["awayData"]
    hd, ad = h.get("division"), a.get("division")
    same = bool(hd and ad and hd == ad)
    diff = (league_strength(hd) - league_strength(ad)) / 3.0
    factors = [["League strength", diff]]

    # Early-season table is intentionally weak; cross-division positions are ignored.
    if same and h.get("position") and a.get("position"):
        v = (a["position"] - h["position"]) * 2.0
    else:
        v = 0
    diff += v; factors.append(["Current position", v])

    if same and h.get("lastSeasonPosition") and a.get("lastSeasonPosition"):
        v = (a["lastSeasonPosition"] - h["lastSeasonPosition"]) * 1.65
    else:
        v = 0
    diff += v; factors.append(["Last season", v])

    hp, ap = h.get("formPoints"), a.get("formPoints")
    v = ((hp or 0) - (ap or 0)) * 2.5
    diff += v; factors.append(["Recent form", v])

    xh, xa = h.get("xg"), a.get("xg")
    v = ((xh or 0) - (xa or 0)) * 13 if xh is not None and xa is not None else 0
    diff += v; factors.append(["xG", v])

    v = (h.get("transferImpact") or 0) - (a.get("transferImpact") or 0)
    diff += v; factors.append(["Squad change", v])

    home_adv = 6 if same else 3
    diff += home_adv; factors.append(["Home advantage", home_adv])

    h2 = re.findall(r"\d+", str(match.get("h2hSummary", "")))
    v = max(-6, min(6, (int(h2[0]) - int(h2[2])) if len(h2) >= 3 else 0))
    diff += v; factors.append(["H2H", v])

    # Confirmed XI quality is a meaningful late pre-match adjustment.
    hxi, axi = h.get("xiRating"), a.get("xiRating")
    v = ((hxi or 0) - (axi or 0)) * 10 if hxi is not None and axi is not None else 0
    diff += v; factors.append(["Starting XI quality", v])

    # Goal model: league scoring environment + strength split, then optional xG pull.
    comp = str(match.get("competition", ""))
    total = 2.55
    if any(x in comp for x in ("Premier League", "Bundesliga", "Eredivisie")): total = 2.75
    if any(x in comp for x in ("Serie A", "Ligue 1")): total = 2.45
    if "Cup" in comp or "Copa" in comp or "Pokal" in comp: total = 2.65
    share = 1 / (1 + math.exp(-diff / 105))
    lam_h = max(.35, min(3.5, total * (.42 + .34 * share)))
    lam_a = max(.30, min(3.25, total * (.42 + .34 * (1 - share))))
    if xh is not None: lam_h = .65 * lam_h + .35 * max(.20, min(3.5, xh))
    if xa is not None: lam_a = .65 * lam_a + .35 * max(.20, min(3.25, xa))

    ph, pa = poisson(lam_h), poisson(lam_a)
    pH = pD = pA = 0.0
    grid = []
    for i, pi in enumerate(ph):
        for j, pj in enumerate(pa):
            q = pi * pj; grid.append((q, i, j))
            if i > j: pH += q
            elif i == j: pD += q
            else: pA += q
    probs = [pH, pD, pA]
    totalp = sum(probs); probs = [p / totalp for p in probs]
    idx = max(range(3), key=lambda i: probs[i])
    verdict = match["home"] if idx == 0 else "DRAW" if idx == 1 else match["away"]
    # Pick the most likely exact score that is CONSISTENT with the 1X2 verdict.
    allowed = [g for g in grid if (idx==0 and g[1]>g[2]) or (idx==1 and g[1]==g[2]) or (idx==2 and g[1]<g[2])]
    modal = max(allowed or grid, key=lambda x:x[0])
    projected = f"{modal[1]}–{modal[2]}"
    confidence = round(max(42, min(95, 48 + (sorted(probs, reverse=True)[0] - sorted(probs, reverse=True)[1]) * 170)))

    completeness = 35 + (8 if hd else 0) + (8 if ad else 0) + (7 if h.get("form") else 0) + (7 if a.get("form") else 0)
    completeness += 7 if h.get("position") is not None and a.get("position") is not None else 0
    completeness += 7 if h.get("lastSeasonPosition") is not None and a.get("lastSeasonPosition") is not None else 0
    completeness += 7 if xh is not None and xa is not None else 0
    completeness += 7 if h.get("lineup") and a.get("lineup") else 0
    completeness += 5 if h.get("xiRating") is not None and a.get("xiRating") is not None else 0
    return {
        "verdict": f"WIN: {verdict}" if verdict != "DRAW" else "DRAW",
        "confidence": confidence,
        "probabilities": probs,
        "projected": projected,
        "modalScore": f"{modal[1]}–{modal[2]}",
        "expectedGoals": [round(lam_h, 2), round(lam_a, 2)],
        "factors": [[name, round(value, 1)] for name, value in factors],
        "dataCompleteness": min(100, completeness),
        "decisionNote": "League strength + season prior + form/xG + squad change + H2H + XI quality + home effect",
    }


def process_match(m, now, sofa_maps):
    mid = str(pick(m, "id", "matchId") or "")
    home, away = m.get("home") or {}, m.get("away") or {}
    hn, an = pick(home, "name", "longName"), pick(away, "name", "longName")
    if not mid or not hn or not an:
        return None
    base_comp, display_comp, ctry = normalize_comp(m.get("_league_name"), m.get("_ccode"), m.get("_country"))
    if base_comp not in SUPPORTED:
        return None
    try:
        hp = team_payload(home.get("id")); ap = team_payload(away.get("id"))
    except Exception as exc:
        print("Team data failed", mid, exc); hp = {}; ap = {}
    hl, al = current_league(hp), current_league(ap)
    # Current team payload is the source of truth. Avoid extra historical/table calls
    # here because they made a single match capable of blocking the whole matchday.
    hpos = table_position(hp, home.get("id"))
    apos = table_position(ap, away.get("id"))
    hlast = previous_finish(hp, home.get("id"))
    alast = previous_finish(ap, away.get("id"))
    hd = {"id": home.get("id"), "division": hl.get("division"), "leagueId": hl.get("leagueId"),
          "ccode": hl.get("ccode"), "position": hpos, "form": form_from_team(hp, home.get("id")),
          "lastSeasonPosition": hlast, "transferImpact": transfer_impact(hp), "lineup": [], "injuries": []}
    ad = {"id": away.get("id"), "division": al.get("division"), "leagueId": al.get("leagueId"),
          "ccode": al.get("ccode"), "position": apos, "form": form_from_team(ap, away.get("id")),
          "lastSeasonPosition": alast, "transferImpact": transfer_impact(ap), "lineup": [], "injuries": []}
    hd["formPoints"] = sum(3 if x == "W" else 1 if x == "D" else 0 for x in hd["form"])
    ad["formPoints"] = sum(3 if x == "W" else 1 if x == "D" else 0 for x in ad["form"])

    h2h_summary = "Not available from FotMob."
    # Match details are valuable but must never hold the run hostage.
    try:
        detail = match_details(mid)
        hd["lineup"], ad["lineup"] = lineup(detail, hd["id"], ad["id"])
        xh, xa = xg(detail); hd["xg"], ad["xg"] = xh, xa
        h2h_summary = h2h(detail)
    except Exception as exc:
        print("FotMob detail skipped", mid, exc)
        hd["xg"] = ad["xg"] = None

    sofa_event = None; incidents = []; lineup_source = "FotMob" if hd.get("lineup") and ad.get("lineup") else None
    # Only spend lineup requests where they can realistically exist: within 12h of kickoff,
    # live, or already finished. This removes dozens of useless requests for distant fixtures.
    try:
        day_key = (m.get("utcTime") or "")[:10] or now.date().isoformat()
        evmap = sofa_maps.get(day_key, {})
        sofa_event = evmap.get((norm_team_name(hn), norm_team_name(an)))
        if sofa_event:
            sid = sofa_event.get("id")
            kickoff_raw = m.get("utcTime")
            should_fetch_lineup = True
            try:
                if kickoff_raw:
                    k = dt.datetime.fromisoformat(str(kickoff_raw).replace("Z", "+00:00"))
                    should_fetch_lineup = (k - dt.datetime.now(dt.timezone.utc)).total_seconds() <= 12 * 3600
            except Exception:
                pass
            if should_fetch_lineup:
                sofa_lh, sofa_la = sofa_lineups(sid)
                if sofa_lh.get("players") and sofa_la.get("players"):
                    hd["lineup"] = sofa_lh["players"]; ad["lineup"] = sofa_la["players"]
                    hd["bench"] = sofa_lh.get("substitutes", []); ad["bench"] = sofa_la.get("substitutes", [])
                    hd["missingPlayers"] = sofa_lh.get("missingPlayers", []); ad["missingPlayers"] = sofa_la.get("missingPlayers", [])
                    hd["formation"] = sofa_lh.get("formation"); ad["formation"] = sofa_la.get("formation")
                    hd["lineupConfirmed"] = sofa_lh.get("confirmed", False); ad["lineupConfirmed"] = sofa_la.get("confirmed", False)
                    hd["xiRating"] = lineup_quality(sofa_lh); ad["xiRating"] = lineup_quality(sofa_la)
                    lineup_source = "Sofascore"
            # Incidents matter primarily for live/finished games; skip them for future matches.
            if status(m) in ("LIVE", "FT"):
                incidents = sofa_incidents(sid)
    except Exception as exc:
        print("Sofascore enrichment skipped", mid, exc)

    hs, ass = score(m)
    st = m.get("status") or {}
    return {"id": mid, "competition": display_comp, "competitionName": base_comp,
            "competitionCountry": ctry, "competitionCode": str(m.get("_ccode") or "INT").upper(),
            "competitionFlag": flag(m.get("_ccode"), ctry), "home": hn, "away": an,
            "homeScore": hs, "awayScore": ass, "status": status(m),
            "kickoff": st.get("utcTime") or m.get("utcTime"),
            "minute": {"short": pick(st, "reason", "period") or ""},
            "homeData": hd, "awayData": ad, "h2hSummary": h2h_summary, "scorers": incidents,
            "sofascoreEventId": sofa_event.get("id") if sofa_event else None,
            "lineupSource": lineup_source,
            "fotmobMatchUrl": f"{ROOT}/matches/{mid}/match-details"}


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
            errors.append(f"{day}: {exc}"); print("FotMob daily failed", day, exc)

    matches, seen = [], set()
    candidates = []
    for m in raw:
        mid = str(pick(m, "id", "matchId") or "")
        if not mid or mid in seen: continue
        seen.add(mid)
        base_comp = normalize_comp(m.get("_league_name"), m.get("_ccode"), m.get("_country"))[0]
        if base_comp in SUPPORTED: candidates.append(m)

    # One scheduled-events request per day, shared by every match.
    sofa_maps = {}
    for day in days:
        try:
            evs = sofa_scheduled(day)
            sofa_maps[day.isoformat()] = sofa_event_map(evs)
            print(f"Sofascore {day}: {len(evs)} events indexed")
        except Exception as exc:
            sofa_maps[day.isoformat()] = {}
            print("Sofascore schedule skipped", day, exc)

    print(f"PROCESSING {len(candidates)} fixtures with 8 workers")
    # Hard concurrency keeps one slow provider from serially blocking the whole matchday.
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(process_match, m, now, sofa_maps): m for m in candidates}
        for n, fut in enumerate(as_completed(futures), 1):
            try:
                out = fut.result()
                if out:
                    out["model"] = model(out)
                    matches.append(out)
            except Exception as exc:
                m = futures[fut]
                errors.append(f"{pick(m, 'id', 'matchId')}: {exc}")
                print("MATCH FAILED", pick(m, "id", "matchId"), exc)
            if n % 5 == 0 or n == len(futures):
                print(f"PROGRESS {n}/{len(futures)}")

    matches.sort(key=lambda x: (x["status"] != "LIVE", x.get("kickoff") or ""))
    if not matches:
        print("NO NEW FIXTURES GENERATED")
        existing = Path("data/fixtures.json")
        if existing.exists():
            try:
                old = json.loads(existing.read_text(encoding="utf-8"))
                if isinstance(old.get("matches"), list) and old["matches"]:
                    old["sourceStatus"] = "Refresh failed · last valid feed retained"
                    old["sourceErrors"] = errors
                    old["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
                    existing.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
                    return
            except Exception as exc:
                print("Could not preserve previous feed:", exc)
        raise SystemExit(2)

    result = {"updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "fixtureCount": len(matches),
              "sourceStatus": f"FotMob + Sofascore · {len(matches)} fixtures", "sourceErrors": errors, "matches": matches}
    Path("data").mkdir(exist_ok=True)
    Path("data/fixtures.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", len(matches), "fixtures")


if __name__ == "__main__":
    main()
