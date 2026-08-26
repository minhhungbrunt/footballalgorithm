import datetime as dt
import json
import math
import re
import time
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("America/New_York")
ROOT = "https://www.fotmob.com"
APIGW = "https://apigw.fotmob.com"
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


def get(url, params=None, timeout=22, tries=3):
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
        time.sleep(1.2 + attempt)
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


# Competition search terms. Search API returns the current FotMob league ID.
# Country-qualified Premier League names are resolved separately after the search.
LEAGUE_SEARCH = [
    ("Premier League","England"),("Championship","England"),("League One","England"),("League Two","England"),
    ("EFL Cup","England"),("FA Cup","England"),("LaLiga","Spain"),("LaLiga 2","Spain"),("Copa del Rey","Spain"),
    ("Bundesliga","Germany"),("2. Bundesliga","Germany"),("DFB Pokal","Germany"),("Serie A","Italy"),("Serie B","Italy"),
    ("Coppa Italia","Italy"),("Ligue 1","France"),("Ligue 2","France"),("Coupe de France","France"),
    ("Eredivisie","Netherlands"),("KNVB Beker","Netherlands"),("Primeira Liga","Portugal"),
    ("Scottish Premiership","Scotland"),("Belgian Pro League","Belgium"),("Turkish Super Lig","Türkiye"),
    ("Saudi Pro League","Saudi Arabia"),("MLS","United States"),("Liga MX","Mexico"),("Brasileirão","Brazil"),
    ("Liga Argentina","Argentina"),("J1 League","Japan"),("K League 1","South Korea"),("A-League","Australia"),
    ("UEFA Champions League","International"),("UEFA Europa League","International"),
    ("UEFA Conference League","International"),("UEFA Champions League Qualification","International"),
    ("UEFA Europa League Qualification","International"),("UEFA Conference League Qualification","International"),
    ("Copa Libertadores","International"),("Copa Sudamericana","International"),("CONCACAF Champions Cup","International"),
]


def search_league_id(name, country):
    key = ("SEARCH_LEAGUE", name, country)
    if key in CACHE:
        return CACHE[key]
    try:
        r = requests.get(f"{APIGW}/searchapi/suggest", params={"term": name, "lang": "en"}, headers=HEAD, timeout=18)
        r.raise_for_status()
        data = r.json()
        hits = []
        for group in data if isinstance(data, list) else []:
            if not isinstance(group, dict):
                continue
            for item in group.get("suggestions", []) or group.get("options", []) or []:
                payload = item.get("payload") if isinstance(item, dict) else None
                obj = payload if isinstance(payload, dict) else item
                typ = str(obj.get("type") or "").lower()
                lname = str(obj.get("leagueName") or obj.get("name") or "")
                if typ == "league" or lname:
                    hits.append(obj)
        target = name.lower()
        for obj in hits:
            lname = str(obj.get("leagueName") or obj.get("name") or "")
            c = country_name(obj.get("country"), obj.get("ccode") or obj.get("countryCode"))
            if lname.lower() == target and (country == "International" or c.lower() == country.lower()):
                lid = obj.get("id") or obj.get("leagueId")
                if lid:
                    CACHE[key] = int(lid)
                    return int(lid)
        for obj in hits:
            lname = str(obj.get("leagueName") or obj.get("name") or "")
            if lname.lower() == target:
                lid = obj.get("id") or obj.get("leagueId")
                if lid:
                    CACHE[key] = int(lid)
                    return int(lid)
    except Exception as exc:
        print("League search failed", name, country, exc)
    return None


def league_page_matches(league_id, day):
    payload = page_json(f"{ROOT}/leagues/{league_id}")
    rows = []
    # Current pageProps shape: fixtures.allMatches. Walk fallback handles minor schema changes.
    candidates = []
    for obj in walk(payload):
        if isinstance(obj, dict):
            allm = obj.get("allMatches")
            if isinstance(allm, list):
                candidates.extend(allm)
    seen = set()
    wanted = day.strftime("%Y-%m-%d")
    for m in candidates:
        if not isinstance(m, dict):
            continue
        mid = str(pick(m, "id","matchId") or "")
        if not mid or mid in seen:
            continue
        st = m.get("status") or {}
        utc = pick(st, "utcTime") or m.get("utcTime")
        if not utc or str(utc)[:10] != wanted:
            continue
        if st.get("cancelled"):
            continue
        seen.add(mid)
        rows.append(m)
    return rows


def daily(day):
    """Build today's fixtures from FotMob's current search + server-rendered league pages.

    The legacy www.fotmob.com/api/matches route is intentionally NOT used here.
    Current FotMob data is exposed through apigw search plus server-rendered league pages.
    """
    all_rows = []
    errors = []
    for name, country in LEAGUE_SEARCH:
        lid = search_league_id(name, country)
        if not lid:
            errors.append(f"{name}: league id not found")
            continue
        try:
            rows = league_page_matches(lid, day)
            for m in rows:
                m = dict(m)
                m["_league_name"] = name
                m["_ccode"] = "INT" if country == "International" else None
                m["_country"] = country
                m["_league_id"] = lid
                m["_page_url"] = pick(m, "pageUrl", "matchPageUrl", "url")
                all_rows.append(m)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    # Return the same wrapper shape as the old daily parser.
    return {"matches": all_rows, "_errors": errors}

def extract_next_data(html):
    marker = '__NEXT_DATA__'
    i = html.find(marker)
    if i < 0:
        raise RuntimeError('__NEXT_DATA__ not found')
    start = html.find('>', i)
    end = html.find('</script>', start)
    if start < 0 or end < 0:
        raise RuntimeError('__NEXT_DATA__ script boundaries not found')
    wrapper = json.loads(html[start + 1:end])
    props = wrapper.get('props', {}).get('pageProps')
    if props is None:
        raise RuntimeError('pageProps missing')
    return props


def page_json(url, timeout=25):
    key = ('PAGE', url)
    if key in CACHE:
        return CACHE[key]
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers={**HEAD, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}, timeout=timeout)
            if r.ok:
                value = extract_next_data(r.text)
                CACHE[key] = value
                return value
            last = f"HTTP {r.status_code}"
        except Exception as exc:
            last = str(exc)
        time.sleep(1.0 + attempt)
    raise RuntimeError(f"{url}: {last or 'request failed'}")


def slugify(name):
    x = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    x = re.sub(r"[^a-z0-9]+", "-", x).strip("-")
    return x or "team"


def match_details(match_id, page_url=None, home=None, away=None):
    key = str(match_id)
    if key in DETAIL_CACHE:
        return DETAIL_CACHE[key]
    urls = []
    if page_url:
        if page_url.startswith("http"):
            urls.append(page_url)
        elif page_url.startswith("/"):
            urls.append(ROOT + page_url)
    # The daily match payload normally includes pageUrl. This slug fallback is useful
    # for older/partial payloads; FotMob redirects to the canonical match page.
    urls.append(f"{ROOT}/match/{key}")
    if home and away:
        urls.append(f"{ROOT}/matches/{slugify(home)}-vs-{slugify(away)}")
    errors = []
    for url in urls:
        try:
            value = page_json(url)
            DETAIL_CACHE[key] = value
            return value
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    # Last resort: old endpoint, only if FotMob restores it.
    try:
        value = get(f"{ROOT}/api/matchDetails", {"matchId": key})
        DETAIL_CACHE[key] = value
        return value
    except Exception as exc:
        errors.append(str(exc))
    raise RuntimeError("match detail unavailable: " + " | ".join(errors))


def team_payload(team_id, team_name=""):
    key = str(team_id)
    if key not in TEAM_CACHE:
        url = f"{ROOT}/teams/{key}/overview/{slugify(team_name)}"
        try:
            TEAM_CACHE[key] = page_json(url)
        except Exception as exc:
            print("Team page failed", key, exc)
            TEAM_CACHE[key] = {}
    return TEAM_CACHE[key]


def league_payload(league_id, league_name=""):
    key = str(league_id)
    if not league_id:
        return {}
    if key not in LEAGUE_CACHE:
        # FotMob's /api/leagues JSON route is no longer reliable. The league page
        # contains current table/fixture data in its server-rendered pageProps.
        try:
            LEAGUE_CACHE[key] = page_json(f"{ROOT}/leagues/{key}")
        except Exception as exc:
            print("League page failed", key, exc)
            LEAGUE_CACHE[key] = {}
    return LEAGUE_CACHE[key]


def match_rows(day_payload):
    if isinstance(day_payload, dict) and isinstance(day_payload.get("matches"), list):
        return [dict(x) for x in day_payload["matches"] if isinstance(x, dict)]
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
            match["_page_url"] = pick(match, "pageUrl", "matchPageUrl", "url")
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
    # FotMob team pages expose primaryLeagueId/primaryLeagueName and memberOf data.
    # We deliberately read the team's own page, never the cup fixture's competition.
    candidates = []
    for obj in walk(payload):
        if not isinstance(obj, dict):
            continue
        pid = pick(obj, "primaryLeagueId", "leagueId")
        pname = pick(obj, "primaryLeagueName", "leagueName", "division")
        if pid and pname:
            candidates.append({"division": str(pname), "leagueId": pid, "ccode": pick(obj, "ccode", "countryCode")})
        member = obj.get("memberOf")
        if isinstance(member, dict):
            pid = pick(member, "leagueId", "id")
            pname = pick(member, "leagueName", "name")
            if pid and pname:
                candidates.append({"division": str(pname), "leagueId": pid, "ccode": pick(member, "ccode", "countryCode")})
    # Prefer a normal domestic league over a cup/European competition.
    for c in candidates:
        name = c["division"].lower()
        if not any(x in name for x in ("cup", "champions", "europa", "conference", "friendly", "relegation")):
            return c
    return candidates[0] if candidates else {"division": None, "leagueId": None, "ccode": None}

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
    # The old season API is unreliable. Try a current team-page history node first.
    for payload in list(TEAM_CACHE.values()):
        pos = previous_finish(payload, team_id)
        if pos is not None:
            return pos
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
    # Current pageProps uses content.lineup.homeTeam / awayTeam. Keep support for
    # the older lineups[] shape as a fallback.
    content = detail.get("content") if isinstance(detail, dict) else None
    lu = content.get("lineup") if isinstance(content, dict) else None
    if isinstance(lu, dict):
        for side, tid in (("homeTeam", home_id), ("awayTeam", away_id)):
            team = lu.get(side)
            if isinstance(team, dict):
                players = team.get("players") or team.get("starters") or team.get("lineup") or []
                for player in players:
                    if not isinstance(player, dict):
                        continue
                    p = player.get("player") if isinstance(player.get("player"), dict) else player
                    name = pick(p, "name", "playerName")
                    if not name:
                        continue
                    result[str(tid)].append({
                        "name": name,
                        "position": pick(player, "position", "role", "positionName") or pick(p, "usualPosition","position","role"),
                        "rating": pick(player, "rating", "matchRating") or pick(p, "rating","matchRating"),
                        "starter": player.get("starter", True),
                    })
    if not any(result.values()):
        for obj in walk(detail):
            if not isinstance(obj, dict):
                continue
            teams = obj.get("lineups")
            if not isinstance(teams, list):
                continue
            for team in teams:
                if not isinstance(team, dict):
                    continue
                tid = pick(team, "teamId", "id")
                if tid is None or str(tid) not in result:
                    continue
                for player in team.get("players") or []:
                    if not isinstance(player, dict):
                        continue
                    p = player.get("player") if isinstance(player.get("player"), dict) else player
                    name = pick(p, "name", "playerName")
                    if name:
                        result[str(tid)].append({
                            "name": name,
                            "position": pick(player, "position","role","positionName") or pick(p,"usualPosition","position","role"),
                            "rating": pick(player, "rating","matchRating") or pick(p,"rating","matchRating"),
                            "starter": player.get("starter", True),
                        })
    for key in result:
        seen = set(); clean = []
        for p in result[key]:
            if p["name"] in seen:
                continue
            seen.add(p["name"]); clean.append(p)
        result[key] = clean[:18]
    return result[str(home_id)], result[str(away_id)]

def xg(detail):
    content = detail.get("content") if isinstance(detail, dict) else None
    periods = (((content or {}).get("stats") or {}).get("Periods") or {}) if isinstance(content, dict) else {}
    all_stats = periods.get("All") or {}
    groups = all_stats.get("stats") if isinstance(all_stats, dict) else None
    for group in groups or []:
        if not isinstance(group, dict):
            continue
        for stat in group.get("stats") or []:
            if not isinstance(stat, dict):
                continue
            title = str(stat.get("title") or "").lower()
            if "expected goals" in title or title == "xg":
                vals = stat.get("stats")
                if isinstance(vals, list) and len(vals) >= 2:
                    return as_num(vals[0]), as_num(vals[1])
                return as_num(stat.get("home")), as_num(stat.get("away"))
    # Fallback to recursive search used by older payloads.
    for obj in walk(detail):
        if isinstance(obj, dict) and str(obj.get("title","")).lower() in {"expected goals (xg)","expected goals","xg"}:
            vals = obj.get("stats")
            if isinstance(vals,list) and len(vals)>=2:
                return as_num(vals[0]), as_num(vals[1])
    return None, None

def h2h(detail):
    content = detail.get("content") if isinstance(detail, dict) else None
    h = content.get("h2h") if isinstance(content, dict) else None
    if h:
        text = json.dumps(h, ensure_ascii=False)
        # Prefer a compact record if FotMob provides wins/draws fields.
        wins = re.findall(r'"(?:wins|win|homeWins)"\s*:\s*(\d+)', text)
        draws = re.findall(r'"(?:draws|draw)"\s*:\s*(\d+)', text)
        losses = re.findall(r'"(?:losses|awayWins)"\s*:\s*(\d+)', text)
        if wins and draws and losses:
            return f"{wins[0]}–{draws[0]}–{losses[0]}"
        return text[:450]
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
    modal = max(grid, key=lambda x: x[0])
    projected = f"{max(0, min(5, round(lam_h)))}–{max(0, min(5, round(lam_a)))}"
    confidence = round(max(42, min(95, 48 + (sorted(probs, reverse=True)[0] - sorted(probs, reverse=True)[1]) * 170)))

    completeness = 35 + (8 if hd else 0) + (8 if ad else 0) + (7 if h.get("form") else 0) + (7 if a.get("form") else 0)
    completeness += 7 if h.get("position") is not None and a.get("position") is not None else 0
    completeness += 7 if h.get("lastSeasonPosition") is not None and a.get("lastSeasonPosition") is not None else 0
    completeness += 7 if xh is not None and xa is not None else 0
    completeness += 7 if h.get("lineup") and a.get("lineup") else 0
    return {
        "verdict": f"WIN: {verdict}" if verdict != "DRAW" else "DRAW",
        "confidence": confidence,
        "probabilities": probs,
        "projected": projected,
        "modalScore": f"{modal[1]}–{modal[2]}",
        "expectedGoals": [round(lam_h, 2), round(lam_a, 2)],
        "factors": [[name, round(value, 1)] for name, value in factors],
        "dataCompleteness": min(100, completeness),
        "decisionNote": "League strength + early-season baseline + form/xG + squad change + H2H + small home effect",
    }


def main():
    now = dt.datetime.now(dt.timezone.utc).astimezone(TZ)
    days = [now.date(), now.date() + dt.timedelta(days=1)]
    raw, errors = [], []
    for day in days:
        try:
            payload = daily(day)
            rows = match_rows(payload)
            day_errors = payload.get("_errors", []) if isinstance(payload, dict) else []
            errors.extend([f"{day}: {e}" for e in day_errors])
            print(f"FotMob {day}: {len(rows)} raw fixtures")
            raw.extend(rows)
        except Exception as exc:
            errors.append(f"{day}: {exc}")
            print("FotMob daily failed", day, exc)

    matches, seen = [], set()
    for m in raw:
        mid = str(pick(m, "id", "matchId") or "")
        if not mid or mid in seen: continue
        seen.add(mid)
        home, away = m.get("home") or {}, m.get("away") or {}
        hn, an = pick(home, "name", "longName"), pick(away, "name", "longName")
        if not hn or not an: continue

        base_comp, display_comp, ctry = normalize_comp(m.get("_league_name"), m.get("_ccode"), m.get("_country"))
        if base_comp not in SUPPORTED: continue

        domestic_comp = base_comp in {
            "Premier League","Championship","League One","League Two","LaLiga","LaLiga 2",
            "Bundesliga","2. Bundesliga","Serie A","Serie B","Ligue 1","Ligue 2","Eredivisie",
            "Primeira Liga","Scottish Premiership","Belgian Pro League","Turkish Super Lig",
            "Saudi Pro League","Brasileirão","Liga MX","Liga Argentina","MLS","J1 League",
            "K League 1","A-League","Colombian Primera A"
        }
        hp = ap = {}
        if domestic_comp:
            # This is a league fixture, so the fixture's league is the team's current league.
            hl = {"division": base_comp, "leagueId": m.get("_league_id"), "ccode": m.get("_ccode")}
            al = {"division": base_comp, "leagueId": m.get("_league_id"), "ccode": m.get("_ccode")}
        else:
            hp = team_payload(home.get("id"), hn)
            ap = team_payload(away.get("id"), an)
            hl, al = current_league(hp), current_league(ap)

        hleague = league_payload(hl.get("leagueId"), hl.get("division")) if hl.get("leagueId") else {}
        aleague = hleague if al.get("leagueId") == hl.get("leagueId") else (league_payload(al.get("leagueId"), al.get("division")) if al.get("leagueId") else {})
        hpos = table_position(hleague, home.get("id")) or table_position(hp, home.get("id"))
        apos = table_position(aleague, away.get("id")) or table_position(ap, away.get("id"))
        hlast = previous_finish(hp, home.get("id")) or historical_position(hl.get("leagueId"), home.get("id"))
        alast = previous_finish(ap, away.get("id")) or historical_position(al.get("leagueId"), away.get("id"))
        if hlast is None and not hp:
            hp = team_payload(home.get("id"), hn)
            hlast = previous_finish(hp, home.get("id")) or historical_position(hl.get("leagueId"), home.get("id"))
        if alast is None and not ap:
            ap = team_payload(away.get("id"), an)
            alast = previous_finish(ap, away.get("id")) or historical_position(al.get("leagueId"), away.get("id"))
        hd = {
            "id": home.get("id"), "division": hl.get("division"), "leagueId": hl.get("leagueId"),
            "ccode": hl.get("ccode"), "position": hpos,
            "form": form_from_team(hp, home.get("id")), "lastSeasonPosition": hlast,
            "transferImpact": transfer_impact(hp), "lineup": [], "injuries": []
        }
        ad = {
            "id": away.get("id"), "division": al.get("division"), "leagueId": al.get("leagueId"),
            "ccode": al.get("ccode"), "position": apos,
            "form": form_from_team(ap, away.get("id")), "lastSeasonPosition": alast,
            "transferImpact": transfer_impact(ap), "lineup": [], "injuries": []
        }
        hd["formPoints"] = sum(3 if x == "W" else 1 if x == "D" else 0 for x in hd["form"])
        ad["formPoints"] = sum(3 if x == "W" else 1 if x == "D" else 0 for x in ad["form"])

        try:
            detail = match_details(mid, m.get("_page_url"), hn, an)
            hd["lineup"], ad["lineup"] = lineup(detail, hd["id"], ad["id"])
            xh, xa = xg(detail); hd["xg"], ad["xg"] = xh, xa
            h2h_summary = h2h(detail)
        except Exception as exc:
            print("Detail failed", mid, exc); detail = {}; h2h_summary = "Not available from FotMob."
            hd["xg"] = ad["xg"] = None

        hs, ass = score(m)
        st = m.get("status") or {}
        out = {
            "id": mid, "competition": display_comp, "competitionName": base_comp,
            "competitionCountry": ctry, "competitionCode": str(m.get("_ccode") or "INT").upper(),
            "competitionFlag": flag(m.get("_ccode"), ctry),
            "home": hn, "away": an, "homeScore": hs, "awayScore": ass, "status": status(m),
            "kickoff": st.get("utcTime") or m.get("utcTime"),
            "minute": {"short": pick(st, "reason", "period") or ""},
            "homeData": hd, "awayData": ad, "h2hSummary": h2h_summary,
            "fotmobMatchUrl": (ROOT + m["_page_url"]) if isinstance(m.get("_page_url"), str) and m["_page_url"].startswith("/") else (m.get("_page_url") or f"{ROOT}/matches/{mid}/match-details"),
        }
        out["model"] = model(out)
        matches.append(out)

    matches.sort(key=lambda x: (x["status"] != "LIVE", x.get("kickoff") or ""))
    if not matches:
        print("NO NEW FIXTURES GENERATED")
        if errors: print("SOURCE ERRORS:", " | ".join(errors))
        existing = Path("data/fixtures.json")
        if existing.exists():
            try:
                old = json.loads(existing.read_text(encoding="utf-8"))
                if isinstance(old.get("matches"), list) and old["matches"]:
                    print("KEEPING LAST VALID FEED:", len(old["matches"]), "fixtures")
                    old["sourceStatus"] = "FotMob temporarily unavailable · last valid feed retained"
                    old["sourceErrors"] = errors
                    old["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
                    existing.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
                    return
            except Exception as exc:
                print("Could not preserve previous feed:", exc)
        raise SystemExit(2)

    result = {
        "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "fixtureCount": len(matches),
        "sourceStatus": f"FotMob only · {len(matches)} fixtures",
        "sourceErrors": errors,
        "matches": matches,
    }
    Path("data").mkdir(exist_ok=True)
    Path("data/fixtures.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", len(matches), "fixtures")


if __name__ == "__main__":
    main()
