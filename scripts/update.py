import os, re, json, time, math, datetime as dt
from urllib.parse import urlencode
import requests
from bs4 import BeautifulSoup

BASE="https://www.fotmob.com"
HEAD={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36","Accept":"application/json,text/plain,*/*"}
ROT="https://www.rotowire.com/soccer/lineups.php"
HTTP_CACHE={}
RW_CACHE={}
TEAM_CACHE={}
LEAGUE_CACHE={}


# Canonical competition map. Name alone is never trusted: country/region is also considered.
ALIASES={
 "Premier League":"Premier League","LaLiga":"LaLiga","Bundesliga":"Bundesliga","Serie A":"Serie A",
 "Ligue 1":"Ligue 1","Eredivisie":"Eredivisie","Primeira Liga":"Primeira Liga",
 "Championship":"Championship","League One":"League One","League Two":"League Two",
 "Champions League":"UEFA Champions League","Champions League Qualification":"UEFA Champions League Qualification",
 "Europa League":"UEFA Europa League","Europa League Qualification":"UEFA Europa League Qualification",
 "Conference League":"UEFA Conference League","Conference League Qualification":"UEFA Conference League Qualification",
 "EFL Cup":"EFL Cup","FA Cup":"FA Cup","Copa del Rey":"Copa del Rey","DFB Pokal":"DFB Pokal",
 "Coppa Italia":"Coppa Italia","MLS":"MLS","Liga MX":"Liga MX","Saudi Pro League":"Saudi Pro League",
 "Brasileirao":"Brasileirão","Scottish Premiership":"Scottish Premiership","Belgian Pro League":"Belgian Pro League",
 "Turkish Super Lig":"Turkish Super Lig","Ligue 2":"Ligue 2","Serie B":"Serie B","2. Bundesliga":"2. Bundesliga",
 "LaLiga 2":"LaLiga 2"
}
TOP={v for v in ALIASES.values()}

def get(url,params=None,tries=2):
    last=None
    for i in range(tries):
        try:
            r=requests.get(url,params=params,headers=HEAD,timeout=12)
            if r.ok:
                return r.json() if "json" in r.headers.get("content-type","") else r.text
            last=f"HTTP {r.status_code}"
        except Exception as e:last=str(e)
        time.sleep(1+i)
    raise RuntimeError(last or "request failed")

def cached_get(url,params=None):
    key=(url,tuple(sorted((params or {}).items())))
    if key in HTTP_CACHE: return HTTP_CACHE[key]
    value=get(url,params)
    HTTP_CACHE[key]=value
    return value

def walk(obj):
    if isinstance(obj,dict):
        yield obj
        for v in obj.values(): yield from walk(v)
    elif isinstance(obj,list):
        for v in obj: yield from walk(v)

def pick(d,*keys):
    for k in keys:
        if isinstance(d,dict) and d.get(k) not in (None,""): return d[k]
    return None

def daily(date):
    date = date.strftime("%Y%m%d") if hasattr(date,"strftime") else str(date)
    return get(f"{BASE}/api/matches",{"date":date,"timezone":"America/New_York"})

def details(mid):
    return get(f"{BASE}/api/matchDetails",{"matchId":mid})

def team_page(tid):
    key=str(tid)
    if key not in TEAM_CACHE: TEAM_CACHE[key]=get(f"{BASE}/api/teams",{"id":tid})
    return TEAM_CACHE[key]

def canonical_comp(raw,country=""):
    s=str(raw or "").strip()
    # prevent Kuwait/Azerbaijan/etc Premier League from becoming England Premier League
    if s=="Premier League" and country and country.lower() not in {"england","england u21","england u18"}:
        return f"{country} Premier League"
    return ALIASES.get(s,s)

def team_from_general(g,key):
    x=g.get(key) if isinstance(g,dict) else {}
    return x if isinstance(x,dict) else {}

def form_from_matches(items,team_id):
    out=[]
    for x in items or []:
        h=pick(x,"homeTeam","home")
        a=pick(x,"awayTeam","away")
        hs=pick(x,"homeScore","homeGoals")
        as_=pick(x,"awayScore","awayGoals")
        try:
            hid=str(h.get("id")); aid=str(a.get("id"))
        except: continue
        if str(team_id) not in (hid,aid): continue
        if hs is None or as_ is None: continue
        try:
            hs,as_=int(hs),int(as_)
        except: continue
        if str(team_id)==hid: out.append("W" if hs>as_ else "D" if hs==as_ else "L")
        else: out.append("W" if as_>hs else "D" if hs==as_ else "L")
    return "".join(out[-5:])

def form_pts(f): return sum(3 if x=="W" else 1 if x=="D" else 0 for x in f)

def extract_team(d,tid):
    # Generic extraction because FotMob response shapes can evolve.
    matches=[]
    for o in walk(d):
        if isinstance(o,dict) and ("homeTeam" in o or "awayTeam" in o) and ("homeScore" in o or "awayScore" in o):
            matches.append(o)
    f=form_from_matches(matches,tid)
    pos=None; division=None
    for o in walk(d):
        if isinstance(o,dict):
            if pos is None and str(o.get("teamId",""))==str(tid) and isinstance(o.get("position"),int): pos=o["position"]
            if division is None and isinstance(o.get("leagueName"),str): division=o["leagueName"]
    return {"form":f or "—","formPoints":form_pts(f) if f else None,"position":pos,"division":division}

def extract_lineup(detail,side):
    arr=[]
    for o in walk(detail):
        if isinstance(o,dict):
            # Common FotMob player objects
            if "players" in o and isinstance(o["players"],list):
                for p in o["players"]:
                    if isinstance(p,dict) and pick(p,"name","playerName"):
                        arr.append({"name":pick(p,"name","playerName"),"position":pick(p,"position","role")})
            if "lineup" in o and isinstance(o["lineup"],list):
                for p in o["lineup"]:
                    if isinstance(p,dict) and pick(p,"name","playerName"):
                        arr.append({"name":pick(p,"name","playerName"),"position":pick(p,"position","role")})
    # de-dupe
    seen=set();out=[]
    for p in arr:
        if p["name"] not in seen: seen.add(p["name"]);out.append(p)
    return out[:11]

def current_league_from_team(payload):
    candidates=[]
    for o in walk(payload):
        if not isinstance(o,dict): continue
        for k in ("mainLeague","primaryLeague","currentLeague"):
            x=o.get(k)
            if isinstance(x,dict) and (x.get("name") or x.get("leagueName")):
                candidates.append(x)
        if o.get("leagueName") and (o.get("leagueId") or o.get("id")):
            candidates.append(o)
    for x in candidates:
        name=pick(x,"name","leagueName")
        lid=pick(x,"id","leagueId")
        if name and lid: return {"division":name,"leagueId":lid}
    return {"division":None,"leagueId":None}

def table_position(league_payload,team_id):
    for o in walk(league_payload):
        if isinstance(o,dict):
            tid=o.get("id") or o.get("teamId")
            if tid is not None and str(tid)==str(team_id):
                pos=pick(o,"idx","position","rank")
                if isinstance(pos,(int,float)): return int(pos)
    return None

def extract_h2h(detail):
    for o in walk(detail):
        if not isinstance(o,dict): continue
        h=o.get("h2h")
        if isinstance(h,dict):
            summary=pick(h,"summary","results","form")
            if isinstance(summary,list) and len(summary)>=3:
                try:return f"H2H summary {summary[0]}–{summary[1]}–{summary[2]} (as supplied by FotMob)."
                except: pass
            if isinstance(summary,str): return summary
    return "Not available from FotMob."

def extract_xg(detail,side):
    for o in walk(detail):
        if isinstance(o,dict):
            if side in o and isinstance(o[side],dict):
                x=pick(o[side],"xg","expectedGoals")
                if x is not None:return x
            if o.get("name","").lower() in {"expected goals","xg"}:
                v=pick(o,side,"value")
                if v is not None:return v
    return None

def rw_page(league):
    code={"Premier League":"EPL","UEFA Champions League":"UCL","LaLiga":"LALIGA","Serie A":"SERIEA","Bundesliga":"BUNDESLIGA","Ligue 1":"LIGUE1","MLS":"MLS","Liga MX":"LIGAMX"}.get(league)
    return f"{ROT}?league={code}" if code else ROT

def rotowire(team,league):
    url=rw_page(league)
    try:
        if url in RW_CACHE:
            html=RW_CACHE[url]
        else:
            html=get(url)
            RW_CACHE[url]=html
        if not isinstance(html,str): return [],[],url
        soup=BeautifulSoup(html,"html.parser")
        text=soup.get_text("\n",strip=True)
        # Capture a conservative team block; RotoWire is supplementary and its page can change.
        i=text.lower().find(team.lower())
        if i<0:return [],[],url
        block=text[i:i+6000]
        injuries=[]
        for nm,status in re.findall(r"([A-Z][A-Za-zÀ-ÿ.' -]{2,40})\s+(QUES|OUT|SUS)",block):
            injuries.append({"name":nm.strip(),"status":status})
        players=[]
        positions={"GK","DL","DC","DR","DMC","MC","ML","MR","AML","AMC","AMR","FW","F","M","D"}
        for line in block.splitlines():
            line=line.strip()
            if not line:continue
            if line in positions: continue
            # keep names after common position tokens
            m=re.match(r"^(GK|DL|DC|DR|DMC|MC|ML|MR|AML|AMC|AMR|FW|F|M|D)\s+(.+)$",line)
            if m: players.append({"position":m.group(1),"name":m.group(2).strip()})
            if len(players)>=11:break
        return players,injuries,url
    except Exception:
        return [],[],url

def model(m):
    h,a=m["homeData"],m["awayData"]
    # Strongly structured but match-specific. Cross-division position is not compared directly.
    strength={"Premier League":1880,"LaLiga":1860,"Bundesliga":1855,"Serie A":1845,"Ligue 1":1805,"UEFA Champions League":1880,
      "Championship":1645,"League One":1405,"League Two":1260,"Eredivisie":1685,"Primeira Liga":1695,"MLS":1560,
      "Saudi Pro League":1610,"Brasileirão":1650,"Liga MX":1605,"Scottish Premiership":1585}
    hs=strength.get(h.get("division"),1500); as_=strength.get(a.get("division"),1500)
    diff=(hs-as_)/4
    same=h.get("division") and h.get("division")==a.get("division")
    if same and h.get("position") and a.get("position"):
        diff += (int(a["position"])-int(h["position"]))*3.2
    diff += ((h.get("formPoints") or 0) - (a.get("formPoints") or 0))*(2.5 if not same else 4.0)
    # small venue effect only
    diff += 7 if same else 2
    # lineups and injuries
    diff += (len(h.get("lineup",[]))-len(a.get("lineup",[])))*0.5
    diff += (len(a.get("injuries",[]))-len(h.get("injuries",[])))*1.5
    # H2H is deliberately capped/low-weight because old meetings can be stale.
    hs2h=str(m.get("h2hSummary", ""))
    nums=re.findall(r"\d+", hs2h)
    if len(nums)>=3:
        try: diff += (int(nums[0])-int(nums[2]))*1.5
        except: pass
    # Draw rises when teams are close.
    draw=0.25 + 0.15*math.exp(-abs(diff)/60)
    wm=1-draw
    ph=1/(1+math.exp(-diff/55))*wm
    pa=wm-ph
    p=[ph,draw,pa];s=sum(p);p=[x/s for x in p]
    idx=max(range(3),key=lambda i:p[i])
    verdict=m["home"] if idx==0 else "DRAW" if idx==1 else m["away"]
    verdict="WIN: "+verdict if verdict!="DRAW" else "DRAW"
    reasons=[
      f"{h.get('division','Division unavailable')} vs {a.get('division','Division unavailable')}; division strength is the primary structural input.",
      f"Recent form: {m['home']} {h.get('form','—')} ({h.get('formPoints','—')}/15) vs {m['away']} {a.get('form','—')} ({a.get('formPoints','—')}/15).",
      ("Same-division table positions are compared directly." if same else "Different divisions: raw league positions are NOT compared; a lower-tier team is not treated as equal simply because it has a similar rank."),
      f"Home advantage is intentionally small ({7 if same else 3} rating points).",
      f"RotoWire lineup availability: {len(h.get('lineup',[]))} / 11 vs {len(a.get('lineup',[]))} / 11; injuries listed {len(h.get('injuries',[]))} vs {len(a.get('injuries',[]))}."
    ]
    conf=min(94,max(42,50+abs(p[idx]-sorted(p,reverse=True)[1])*120))
    return {"verdict":verdict,"confidence":conf,"probabilities":p,"projected":"1–1" if idx==1 else "1–0" if idx==0 else "0–1","reasons":reasons,"dataCompleteness":min(100,45+sum(bool(v) for v in [h.get("division"),a.get("division"),h.get("position"),a.get("position"),h.get("form"),a.get("form")])*9)}

def main():
    today=dt.datetime.now(dt.timezone.utc).astimezone().date()
    dates=[today, today+dt.timedelta(days=1)]
    raw=[]; errors=[]
    for d in dates:
        try:
            x=daily(d)
            for lg in x.get("leagues",[]):
                for m in lg.get("matches",[]): raw.append((lg,m))
        except Exception as e:
            errors.append(f"{d}: {e}"); print("FotMob daily failed",d,e)
    matches=[]
    seen=set()
    for lg,m in raw:
        mid=str(m.get("id") or m.get("matchId") or "")
        if not mid or mid in seen:continue
        seen.add(mid)
        gen=m.get("general",m)
        home=pick(m,"homeTeam","home") or {}
        away=pick(m,"awayTeam","away") or {}
        hn=pick(home,"name","longName","teamName") or m.get("homeTeamName")
        an=pick(away,"name","longName","teamName") or m.get("awayTeamName")
        if not hn or not an:continue
        comp=canonical_comp(lg.get("name") or m.get("competitionName"),lg.get("country",{}).get("name","") if isinstance(lg.get("country"),dict) else "")
        if comp not in TOP: continue
        try:d=details(mid)
        except Exception as e:d={}
        hid=home.get("id") or m.get("homeTeamId"); aid=away.get("id") or m.get("awayTeamId")
        try:
            htp=team_page(hid) if hid else {}
            hp=extract_team(htp,hid) if hid else {}
            hlg=current_league_from_team(htp)
            hp.update(hlg); hp["id"]=hid
        except Exception: hp={}
        try:
            atp=team_page(aid) if aid else {}
            ap=extract_team(atp,aid) if aid else {}
            alg=current_league_from_team(atp)
            ap.update(alg); ap["id"]=aid
        except Exception: ap={}
        # Never use the cup competition as a club's domestic division.
        for td in (hp,ap):
            if td.get("leagueId"):
                try: td["position"]=table_position(cached_get(f"{BASE}/api/leagues",{"id":td["leagueId"]}), td.get("id"))
                except Exception: pass
        hp["lineup"],hp["injuries"],rw=rotowire(hn,comp)
        ap["lineup"],ap["injuries"],rw2=rotowire(an,comp)
        hp["xg"]=extract_xg(d,"home");ap["xg"]=extract_xg(d,"away")
        st=m.get("status",{}) if isinstance(m.get("status",{}),dict) else {}
        hs=pick(home,"score") if isinstance(home,dict) else None
        aws=pick(away,"score") if isinstance(away,dict) else None
        scorestr=pick(st,"scoreStr")
        if (hs is None or aws is None) and isinstance(scorestr,str):
            mm=re.match(r"\s*(\d+)\s*[-:]\s*(\d+)\s*",scorestr)
            if mm: hs,aws=int(mm.group(1)),int(mm.group(2))
        out={"id":mid,"competition":comp,"competitionCode":str(lg.get("ccode") or comp[:3]).upper(),"home":hn,"away":an,
             "homeScore":hs,"awayScore":aws,
             "status":"LIVE" if st.get("started") and not st.get("finished") else "FT" if st.get("finished") else "UPCOMING",
             "kickoff":st.get("utcTime") or m.get("time"),"minute":pick(st,"period","reason"),
             "homeData":hp,"awayData":ap,"rotowireUrl":rw if rw!=ROT else rw2,
             "h2hSummary":extract_h2h(d)}
        out["model"]=model(out);matches.append(out)
    matches.sort(key=lambda x:(x["status"]!="LIVE",x.get("kickoff") or ""))
    if not matches:
        print("NO FIXTURES GENERATED")
        if errors: print("SOURCE ERRORS:"," | ".join(errors))
        raise SystemExit(2)
    result={"updatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"fixtureCount":len(matches),
            "sourceStatus":f"FotMob OK · RotoWire checked · {len(matches)} fixtures",
            "sourceErrors":errors,"matches":matches}
    Path("data/fixtures.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("WROTE",len(matches),"fixtures")

if __name__=="__main__": main()
