const DATA_URL="data/fixtures.json";
let DATA=null, filter="ALL", openId=null, lastPollAt=null;

const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const n=x=>Number.isFinite(Number(x))?Number(x):null;
const clean=x=>String(x??"").trim();
const unavailable=x=>x==null||clean(x)===""||["—","--","none","null"].includes(clean(x).toLowerCase());
const nice=(x,f="Not available")=>unavailable(x)?f:String(x);
const pct=x=>Math.round((Number(x)||0)*100)+"%";
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const td=(m,s)=>s==="home"?(m.homeData||{}):(m.awayData||{});
const isDraw=v=>clean(v).toUpperCase()==="DRAW"||clean(v).toUpperCase().startsWith("DRAW");
const status=m=>clean(m.status).toUpperCase();

function formPills(f){
  const a=clean(f).replace(/[^WDL]/gi,"").toUpperCase().slice(-5).split("");
  return a.length?a.map(x=>`<i class="pill ${x}">${x}</i>`).join(""):`<span class="note">No five-match sample yet</span>`;
}
function pos(d){return d.position!=null?`#${d.position}`:"Position not available"}
function time(m){
  if(status(m)==="LIVE")return `<b class="time live">LIVE${m.minute&&m.minute.short?` · ${esc(m.minute.short)}`:""}</b>`;
  if(status(m)==="FT")return `<b class="time">FT</b>`;
  if(!m.kickoff)return `<span class="time">Time unavailable</span>`;
  const z=new Date(m.kickoff); return `<span class="time">${z.toLocaleTimeString([], {hour:"numeric",minute:"2-digit"})}</span>`;
}
function score(m){
  return m.homeScore!=null&&m.awayScore!=null?`${esc(m.homeScore)} : ${esc(m.awayScore)}`:"— : —";
}
function verdictClass(v){return isDraw(v)?"draw":""}

function lineup(d,name){
  const list=Array.isArray(d.lineup)?d.lineup:[];
  const bench=Array.isArray(d.bench)?d.bench:[];
  const missing=Array.isArray(d.missingPlayers)?d.missingPlayers:[];
  if(!list.length)return `<div class="lineup"><h3>${esc(name)} <span class="rank">LINEUP</span></h3><div class="empty-data">Lineup not published yet.</div></div>`;
  const confirmed=d.lineupConfirmed===true;
  const avg=d.xiRating!=null?` · XI ${Number(d.xiRating).toFixed(2)}`:"";
  return `<div class="lineup"><h3>${esc(name)} <span class="rank ${confirmed?'confirmed':''}">${confirmed?'CONFIRMED':'EXPECTED'}${avg}</span></h3>`+
    list.map(p=>`<div class="player"><span class="pos">${esc(nice(p.position,""))}</span><span class="pname">${esc(nice(p.name,"Unknown"))}</span><span class="rating">${p.rating!=null?esc(p.rating):""}</span></div>`).join("")+`<div class="lineup-extra">${bench.length?`Bench: ${bench.slice(0,7).map(x=>esc(x.name)).join(', ')}`:""}${missing.length?`<br>Unavailable: ${missing.slice(0,6).map(x=>esc(x.player?.name||x.name||x.playerName||'Player')).join(', ')}`:""}</div></div>`;
}

function evidence(m){
  const h=td(m,"home"),a=td(m,"away"),items=[];
  if(h.division||a.division)items.push(["DIV","League context",h.division===a.division?`${m.home} and ${m.away} are in ${nice(h.division)}. Positions are comparable.`:`${nice(h.division)} vs ${nice(a.division)}. Raw positions are NOT compared across divisions.`]);
  if(h.position!=null||a.position!=null)items.push(["POS","Current table",`${m.home}: ${pos(h)} · ${m.away}: ${pos(a)}.`]);
  if(h.lastSeasonPosition!=null||a.lastSeasonPosition!=null)items.push(["22","Last season finish",`${m.home}: ${nice(h.lastSeasonPosition,"N/A")} · ${m.away}: ${nice(a.lastSeasonPosition,"N/A")}. Used as an early-season prior.`]);
  if(h.form||a.form)items.push(["FORM","Recent form",`${m.home}: ${nice(h.form,"N/A")} · ${m.away}: ${nice(a.form,"N/A")}.`]);
  if(h.xg!=null||a.xg!=null)items.push(["xG","Expected goals",`${m.home}: ${nice(h.xg)} · ${m.away}: ${nice(a.xg)}.`]);
  if(h.transferImpact!=null||a.transferImpact!=null)items.push(["TR","Squad change",`${m.home}: ${fmtSigned(h.transferImpact)} · ${m.away}: ${fmtSigned(a.transferImpact)}. Rough transfer/squad-strength adjustment.`]);
  if(m.h2hSummary&&!/not available/i.test(m.h2hSummary))items.push(["H2H","Head-to-head",m.h2hSummary]);
  if(h.injuries?.length||a.injuries?.length)items.push(["AVL","Availability",`${m.home}: ${h.injuries.length} listed · ${m.away}: ${a.injuries.length} listed.`]);
  if(!items.length)items.push(["i","Data status","FotMob has not supplied enough secondary data yet. Missing fields are not invented."]);
  return items.map(x=>`<div class="evidence-item"><div class="eicon">${esc(x[0])}</div><div><b>${esc(x[1])}</b><p>${esc(x[2])}</p></div></div>`).join("");
}
function fmtSigned(x){return x==null?"N/A":(Number(x)>0?"+":"")+Number(x).toFixed(1)}

function factors(m){
  const h=td(m,"home"),a=td(m,"away"),r=m.model||{};
  const f=Array.isArray(r.factors)?r.factors:[
    ["League strength",r.leagueStrengthDiff||0],
    ["Current position",r.positionDiff||0],
    ["Last season prior",r.lastSeasonDiff||0],
    ["Recent form",r.formDiff||0],
    ["Squad / transfers",r.transferDiff||0],
    ["xG / attack",r.xgDiff||0],
    ["Home advantage",r.homeAdvantage||0],
    ["H2H",r.h2hDiff||0]
  ];
  return f.map(x=>{
    const v=Number(x[1])||0,w=Math.min(100,Math.abs(v)*2.7);
    return `<div class="factor"><span class="factor-name">${esc(x[0])}</span><span class="meter"><i style="width:${w}%"></i></span><span class="factor-val">${v>0?"+":""}${v.toFixed(1)}</span></div>`;
  }).join("");
}

function comparison(m){
  const h=td(m,"home"),a=td(m,"away");
  const rows=[
    ["League",nice(h.division),nice(a.division)],
    ["Position",pos(h),pos(a)],
    ["Last season",nice(h.lastSeasonPosition),nice(a.lastSeasonPosition)],
    ["Form",nice(h.form,"N/A"),nice(a.form,"N/A")],
    ["xG",nice(h.xg),nice(a.xg)],
    ["Squad change",fmtSigned(h.transferImpact),fmtSigned(a.transferImpact)],
    ["Injuries",h.injuries?.length??0,a.injuries?.length??0],
    ["XI",h.lineup?.length??0,a.lineup?.length??0]
  ];
  return rows.map(r=>`<div class="stat"><span class="l">${esc(r[1])}</span><label>${esc(r[0])}</label><span class="r">${esc(r[2])}</span></div>`).join("");
}

function analysis(m){
  const r=m.model||{},p=r.probabilities||[.33,.34,.33],conf=Math.round(Number(r.confidence)||0),comp=Math.round(Number(r.dataCompleteness)||0);
  const verdict=nice(r.verdict,"MODEL PENDING");
  const h=td(m,"home"),a=td(m,"away");
  return `<div class="analysis-grid">
  <div>
    <div class="panel">
      <div class="ptitle">MODEL DECISION</div>
      <div class="decision ${verdictClass(verdict)}">
        <div><div class="label">${isDraw(verdict)?"DRAW CALL":"BEST OUTCOME"}</div><div class="big">${esc(verdict)}</div>
        <div class="sub">Confidence ${conf}/100 · ${esc(r.decisionNote||"Weighted match model using available FotMob evidence")}</div></div>
        <div class="projected"><small>PROJECTED SCORE</small><b>${esc(nice(r.projected,"N/A"))}</b></div>
      </div>
      <div class="probs">
        <div class="prob"><span>${esc(m.home)}</span><strong>${pct(p[0])}</strong><div class="bar"><i style="width:${p[0]*100}%"></i></div></div>
        <div class="prob"><span>DRAW</span><strong>${pct(p[1])}</strong><div class="bar"><i style="width:${p[1]*100}%"></i></div></div>
        <div class="prob"><span>${esc(m.away)}</span><strong>${pct(p[2])}</strong><div class="bar"><i style="width:${p[2]*100}%"></i></div></div>
      </div>
    </div>
    <div class="panel"><div class="ptitle">MODEL FACTORS</div>${factors(m)}</div>
    <div class="panel"><div class="ptitle">WHY THE MODEL LANDED HERE</div>${evidence(m)}</div>
  </div>
  <div>
    <div class="panel"><div class="ptitle">TEAM SNAPSHOT</div><div class="team-compare">
      <div class="team-card"><h3>${esc(m.home)} <span class="rank">${esc(pos(h))}</span></h3>${comparison(m).split("</div>").slice(0,8).join("</div>")}</div>
      <div class="team-card"><h3>${esc(m.away)} <span class="rank">${esc(pos(a))}</span></h3>${comparison(m).split("</div>").slice(0,8).join("</div>")}</div>
    </div></div>
    <div class="panel"><div class="ptitle">RECENT FORM</div><div class="form-box">
      <div class="form-team"><b>${esc(m.home)}</b><div class="form-line">${formPills(h.form)}</div></div>
      <div class="form-team"><b>${esc(m.away)}</b><div class="form-line">${formPills(a.form)}</div></div>
    </div></div>
    <div class="panel"><div class="ptitle">EARLY-SEASON CONTEXT</div><div class="meta-grid">
      <div class="meta-card"><span>LAST SEASON</span><b>${nice(h.lastSeasonPosition)} vs ${nice(a.lastSeasonPosition)}</b></div>
      <div class="meta-card"><span>TRANSFER / SQUAD PRIOR</span><b>${fmtSigned(h.transferImpact)} vs ${fmtSigned(a.transferImpact)}</b></div>
      <div class="meta-card"><span>H2H</span><b>${esc(nice(m.h2hSummary,"Not available"))}</b></div>
      <div class="meta-card"><span>DATA COMPLETENESS</span><b>${comp}%</b></div>
    </div><div class="note">At the start of a new season, current league position is down-weighted. Last-season finish and squad-change priors carry more weight until enough new matches exist.</div></div>
    <div class="panel"><div class="ptitle">GOALS & ASSISTS</div><div class="scorer-panel">${scorerLine(m)||"No goals yet."}</div></div>
    <div class="panel"><div class="ptitle">STARTING XI</div><div class="lineups">${lineup(h,m.home)}${lineup(a,m.away)}</div>
      <div class="note">Lineups: Sofascore first, FotMob fallback. Confirmed XI is used as a model adjustment.</div></div>
  </div></div>`;
}

function scorerLine(m){
  const s=Array.isArray(m.scorers)?m.scorers:[];
  if(!s.length)return "";
  return `<div class="scorers">${s.map(x=>`<span>⚽ ${esc(x.scorer||'Goal')} ${x.minute!=null?esc(x.minute)+"'":""}${x.assist?` <small>🅰 ${esc(x.assist)}</small>`:""}</span>`).join("")}</div>`;
}
function postMatch(m){
  if(status(m)!=="FT" || m.homeScore==null || m.awayScore==null)return "";
  const v=clean(m.model?.verdict||"").toUpperCase();
  const actual=m.homeScore>m.awayScore?"HOME":m.homeScore<m.awayScore?"AWAY":"DRAW";
  const predicted=v.includes("DRAW")?"DRAW":v.includes(clean(m.home).toUpperCase())?"HOME":v.includes(clean(m.away).toUpperCase())?"AWAY":"";
  if(!predicted)return "";
  if(predicted===actual){
    const exact=String(m.model?.projected||"").replace("–","-")===`${m.homeScore}-${m.awayScore}`;
    return `<div class="post-hit">${exact?"🎯 MODEL NAILED IT":"🟢 MODEL HIT"}${exact?"":" · right result, score missed"}</div>`;
  }
  return `<div class="post-wrong">🤡 MODEL GOT COOKED · called ${esc(v.replace(/^WIN:\s*/,""))}, actual ${actual==="DRAW"?"DRAW":esc(actual==="HOME"?m.home:m.away)}</div>`;
}

function matchHTML(m){
  const r=m.model||{},v=nice(r.verdict,"ANALYSIS PENDING"),open=openId===String(m.id);
  const st=status(m), ended=st==="FT";
  return `<article class="match ${st==="LIVE"?"live":""}" id="m-${esc(m.id)}">
    <div class="match-head">
      <div>${time(m)}</div>
      <div class="teams"><span>${esc(m.home)}</span><span class="vs">vs</span><span>${esc(m.away)}</span></div>
      <div class="score ${m.homeScore==null?"pending":""}">${score(m)}${ended?`<small class="ft-label">FT · MATCH ENDED</small>`:""}</div>
      <div class="verdict ${verdictClass(v)}">${esc(v)}<span class="confidence">${Math.round(Number(r.confidence)||0)}/100</span></div>
      <button class="analyze ${open?"open":""}" onclick="toggleAnalysis('${esc(m.id)}')">${open?"CLOSE":"ANALYZE"}</button>
    </div>
    ${scorerLine(m)}${postMatch(m)}
    <div class="analysis ${open?"open":""}">${analysis(m)}</div>
  </article>`;
}

function render(){
  if(!DATA){$("#fixtures").innerHTML=`<div class="empty">Loading FootballEdge…</div>`;return}
  const stamp=DATA.updatedAt?new Date(DATA.updatedAt):null;
  $("#updated").textContent=stamp?stamp.toLocaleTimeString([], {hour:'numeric',minute:'2-digit',second:'2-digit'}):"—";
  $("#feedStatus").textContent=`${DATA.fixtureCount||0} FIXTURES · ${DATA.sourceStatus||"LIVE FEED"}`;
  const live=(DATA.matches||[]).filter(m=>status(m)==="LIVE");
  $("#liveStrip").innerHTML=live.length?live.map(m=>`<div class="live-card"><div class="tag heartbeat"><i></i> LIVE · ${esc(m.competition)}</div><div class="pair">${esc(m.home)} vs ${esc(m.away)}</div><div class="live-score">${score(m)}</div><div class="min">${esc(m.minute?.short||m.minute?.long||"Live")}</div>${scorerLine(m)}</div>`).join(""):"";
  const comps=[...new Set((DATA.matches||[]).map(m=>m.competition).filter(Boolean))];
  $("#filters").innerHTML=`<button class="filter ${filter==="ALL"?"active":""}" onclick="setFilter('ALL')">ALL</button>`+comps.map(c=>`<button class="filter ${filter===c?"active":""}" onclick='setFilter(${JSON.stringify(c)})'>${esc(c)}</button>`).join("");
  const ms=(DATA.matches||[]).filter(m=>filter==="ALL"||m.competition===filter);
  if(!ms.length){$("#fixtures").innerHTML=`<div class="empty">No matches in this filter.</div>`;return}
  const groups={};ms.forEach(m=>(groups[m.competition]??=[]).push(m));
  $("#fixtures").innerHTML=Object.entries(groups).map(([c,arr])=>`<section class="competition"><div class="comp-head"><span class="comp-logo flag">${esc(arr[0].competitionFlag||'🌍')}</span><div class="comp-title"><h2>${esc(c)}</h2><span class="country-label">${esc(arr[0].competitionCountry||'International')}</span></div><span class="count">${arr.length} MATCH${arr.length===1?"":"ES"}</span></div>${arr.map(matchHTML).join("")}</section>`).join("");
}
function toggleAnalysis(id){
  openId=openId===String(id)?null:String(id);render();
  if(openId)requestAnimationFrame(()=>document.getElementById(`m-${CSS.escape(String(id))}`)?.scrollIntoView({behavior:"smooth",block:"nearest"}));
}
function setFilter(x){filter=x;openId=null;render()}
async function load(){
  try{
    const r=await fetch(`${DATA_URL}?v=${Date.now()}`,{cache:"no-store"});
    if(!r.ok)throw Error(`HTTP ${r.status}`);
    const old=DATA; DATA=await r.json(); render();
    if(old && JSON.stringify(old.matches?.map(x=>[x.id,x.homeScore,x.awayScore]))!==JSON.stringify(DATA.matches?.map(x=>[x.id,x.homeScore,x.awayScore]))) document.title="FootballEdge · Updated";
  }catch(e){ if(!DATA) $("#fixtures").innerHTML=`<div class="error"><b>Football data feed unavailable.</b><br>${esc(e.message)}</div>`; }
}

function mergeLive(events){
  if(!DATA||!Array.isArray(events))return false;
  let changed=false;
  const byPair=new Map(events.map(e=>[`${clean(e.homeTeam?.name)}|${clean(e.awayTeam?.name)}`.toLowerCase(),e]));
  for(const m of DATA.matches||[]){
    const key=`${clean(m.home)}|${clean(m.away)}`.toLowerCase(); const e=byPair.get(key); if(!e)continue;
    const sc=e.homeScore?.current ?? e.homeScore?.normaltime ?? null, ac=e.awayScore?.current ?? e.awayScore?.normaltime ?? null;
    const st=e.status?.type;
    const ns=st==="finished"?"FT":st==="inprogress"?"LIVE":m.status;
    const min=e.status?.description||e.status?.type||m.minute?.short||"";
    if(sc!==null && sc!==m.homeScore){m.homeScore=sc;changed=true} if(ac!==null&&ac!==m.awayScore){m.awayScore=ac;changed=true}
    if(ns!==m.status){m.status=ns;changed=true} m.minute={short:min};
    if(Array.isArray(e.incidents)){
      const goals=e.incidents.filter(i=>i.incidentType==="goal").map(i=>({minute:i.time,added:i.addedTime,team:i.isHome?"home":"away",scorer:i.player?.name,assist:(i.assist1||i.assist2)?.name}));
      if(goals.length){m.scorers=goals;changed=true}
    }
  }
  return changed;
}

async function livePoll(){
  const urls=["https://www.sofascore.com/api/v1/sport/football/events/live","https://api.sofascore.com/api/v1/sport/football/events/live"];
  for(const u of urls){
    try{const r=await fetch(`${u}?v=${Date.now()}`,{cache:"no-store"});if(!r.ok)continue;const j=await r.json();if(mergeLive(j.events||[])){render();}$("#pollStatus").textContent=`● LIVE · ${new Date().toLocaleTimeString([], {hour:'numeric',minute:'2-digit',second:'2-digit'})}`;return;}catch(e){}
  }
}

load();
setInterval(load,30000);
setInterval(livePoll,5000);
setTimeout(livePoll,1000);