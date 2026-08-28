const DATA_URL="data/fixtures.json";
let DATA=null,filter="ALL",openId=null,liveTimer=null,liveCache=new Map(),lastStaticUpdate=null;
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const clean=x=>String(x??"").trim();
const unavailable=x=>x==null||clean(x)===""||["—","--","none","null"].includes(clean(x).toLowerCase());
const nice=(x,f="Not available")=>unavailable(x)?f:String(x);
const pct=x=>Math.round((Number(x)||0)*100)+"%";
const td=(m,s)=>s==="home"?(m.homeData||{}):(m.awayData||{});
const st=m=>clean(m.status).toUpperCase();
const isDraw=v=>clean(v).toUpperCase()==="DRAW";

function formPills(f){const a=clean(f).replace(/[^WDL]/gi,"").toUpperCase().slice(-5).split("");return a.length?a.map(x=>`<i class="pill ${x}">${x}</i>`).join(""):`<span class="note">No recent sample</span>`}
function pos(d){return d.position!=null?`#${esc(d.position)}`:"—"}
function localTime(m){if(!m.kickoff)return "TBD";const d=new Date(m.kickoff);return isNaN(d)?"TBD":d.toLocaleTimeString([], {hour:"numeric",minute:"2-digit"})}
function matchTime(m){const s=st(m);if(s==="LIVE")return `<b class="time live">LIVE${m.minute?.short?` · ${esc(m.minute.short)}`:""}</b>`;if(s==="FT")return `<b class="time">FT · MATCH ENDED</b>`;return `<span class="time">${localTime(m)}</span>`}
function score(m){return m.homeScore!=null&&m.awayScore!=null?`${esc(m.homeScore)} : ${esc(m.awayScore)}`:"— : —"}
function fmtSigned(x){return x==null?"N/A":(Number(x)>0?"+":"")+Number(x).toFixed(1)}
function resultNote(m){if(st(m)!=="FT"||m.homeScore==null||!m.model)return "";const [h,a]=m.model.probabilities||[.33,.34,.33],actual=m.homeScore>m.awayScore?0:m.homeScore===m.awayScore?1:2,pick=m.model.verdict?.startsWith("DRAW")?1:m.model.verdict?.includes(m.home)?0:2;const gap=Math.abs((m.model.expectedGoals?.[0]||0)-m.homeScore)+Math.abs((m.model.expectedGoals?.[1]||0)-m.awayScore);if(actual===pick&&gap<=1.5)return "🎯 MODEL NAILED IT";if(actual===pick)return "🟡 RIGHT CALL · SCORE OFF";if(Math.max(h,a,m.model.probabilities?.[1]||0)<.55)return "🔴 UPSET · MODEL GOT COOKED";return "🤡 MODEL UPDATE: WHAT WAS THAT"}
function scorerLine(m){
  const arr=Array.isArray(m.scorers)?m.scorers:[];
  if(!arr.length)return "";
  return `<div class="scorers">${arr.map(g=>{
    const side=g.team==="home"?m.home:g.team==="away"?m.away:"";
    const og=g.ownGoal?" · OG":"";
    const min=g.minute!=null?`${esc(g.minute)}'`:"";
    const ast=g.assist?` <small>🅰 ${esc(g.assist)}</small>`:"";
    return `<span title="${esc(side)}">⚽ ${esc(g.scorer||"Goal")} ${min}${og}${ast}</span>`;
  }).join("")}</div>`;
}
function lineup(d,name){const list=Array.isArray(d.lineup)?d.lineup:[];const bench=Array.isArray(d.bench)?d.bench:[];if(!list.length)return `<div class="lineup"><h3>${esc(name)}</h3><div class="empty-data">Lineup not published yet.</div></div>`;return `<div class="lineup"><h3>${esc(name)} <span class="rank">${d.lineupConfirmed?"CONFIRMED XI":"EXPECTED XI"}</span></h3>${d.formation?`<div class="formation">${esc(d.formation)}</div>`:""}<div class="player-list">${list.slice(0,18).map(p=>`<div class="player"><span class="pos">${esc(nice(p.position,""))}</span><span class="pname">${esc(nice(p.name,"Unknown"))}</span><span class="rating">${p.rating!=null?esc(p.rating):""}</span></div>`).join("")}</div>${bench.length?`<div class="bench"><b>Bench</b> · ${bench.slice(0,9).map(p=>esc(p.name||"Unknown")).join(", ")}</div>`:""}</div>`}
function recentResults(d){const r=Array.isArray(d.recentResults)?d.recentResults:[];if(!r.length)return `<span class="note">No recent results returned</span>`;return `<div class="recent-results">${r.map(x=>`<div><i class="pill ${esc(x.result)}">${esc(x.result)}</i><span>${esc(x.opponent||"Opponent")}</span><b>${esc(x.gf)}-${esc(x.ga)}</b></div>`).join("")}</div>`}
function evidence(m){const h=td(m,"home"),a=td(m,"away"),items=[];if(h.division||a.division)items.push(["DIV","Current league",`${m.home}: ${nice(h.division)} · ${m.away}: ${nice(a.division)}. Cup competition does not determine domestic division.`]);if(h.position!=null||a.position!=null)items.push(["POS","Current table",`${m.home}: ${pos(h)} · ${m.away}: ${pos(a)}${h.division!==a.division?" · cross-division positions are not directly compared":""}.`]);if(h.lastSeasonPosition!=null||a.lastSeasonPosition!=null)items.push(["25/26","Last season",`${m.home}: ${nice(h.lastSeasonPosition)} · ${m.away}: ${nice(a.lastSeasonPosition)}. Important early-season prior.`]);if(h.form||a.form)items.push(["FORM","Recent form",`${m.home}: ${nice(h.form)} (${h.formPoints||0}/15) · ${m.away}: ${nice(a.form)} (${a.formPoints||0}/15).`]);if(h.xg!=null||a.xg!=null)items.push(["xG","Expected goals",`${m.home}: ${nice(h.xg)} · ${m.away}: ${nice(a.xg)}.`]);if(h.xiRating!=null||a.xiRating!=null)items.push(["XI","Starting XI",`${m.home}: ${nice(h.xiRating)} · ${m.away}: ${nice(a.xiRating)}.`]);if(h.transferImpact!=null||a.transferImpact!=null)items.push(["TR","Squad change",`${m.home}: ${fmtSigned(h.transferImpact)} · ${m.away}: ${fmtSigned(a.transferImpact)}.`]);if(m.h2hSummary&&!/not available/i.test(m.h2hSummary))items.push(["H2H","Head-to-head",m.h2hSummary]);if(!items.length)items.push(["i","Data status","Not enough secondary evidence returned yet."]);return items.map(x=>`<div class="evidence-item"><div class="eicon">${esc(x[0])}</div><div><b>${esc(x[1])}</b><p>${esc(x[2])}</p></div></div>`).join("")}
function factors(m){return (m.model?.factors||[]).map(x=>{const v=Number(x[1])||0,w=Math.min(100,Math.abs(v)*2.4);return `<div class="factor"><span class="factor-name">${esc(x[0])}</span><span class="meter"><i style="width:${w}%"></i></span><span class="factor-val">${v>0?"+":""}${v.toFixed(1)}</span></div>`}).join("")}
function probabilities(m){const p=m.model?.probabilities||[.33,.34,.33];return `<div class="probs"><div class="prob"><span>${esc(m.home)}</span><strong>${pct(p[0])}</strong><div class="bar"><i style="width:${p[0]*100}%"></i></div></div><div class="prob"><span>DRAW</span><strong>${pct(p[1])}</strong><div class="bar"><i style="width:${p[1]*100}%"></i></div></div><div class="prob"><span>${esc(m.away)}</span><strong>${pct(p[2])}</strong><div class="bar"><i style="width:${p[2]*100}%"></i></div></div></div>`}
function analysis(m){const r=m.model||{},h=td(m,"home"),a=td(m,"away"),note=resultNote(m);return `<div class="analysis-grid"><div><div class="panel"><div class="ptitle">MODEL DECISION</div><div class="decision ${isDraw(r.verdict)?"draw":""}"><div><div class="label">BEST OUTCOME</div><div class="big">${esc(nice(r.verdict,"MODEL PENDING"))}</div><div class="sub">Confidence ${esc(r.confidence??0)}/100 · ${esc(r.decisionNote||"")}</div></div><div class="projected"><small>PROJECTED SCORE</small><b>${esc(nice(r.projected))}</b></div></div>${probabilities(m)}${note?`<div class="post-note">${note}</div>`:""}</div><div class="panel"><div class="ptitle">MODEL FACTORS</div>${factors(m)}</div><div class="panel"><div class="ptitle">DEEP EVIDENCE</div>${evidence(m)}</div></div><div><div class="panel"><div class="ptitle">FORM & RESULTS</div><div class="form-box"><div class="form-team"><b>${esc(m.home)} ${formPills(h.form)}</b>${recentResults(h)}</div><div class="form-team"><b>${esc(m.away)} ${formPills(a.form)}</b>${recentResults(a)}</div></div></div><div class="panel"><div class="ptitle">TEAM SNAPSHOT</div><div class="team-compare"><div class="team-card"><h3>${esc(m.home)} <span class="rank">${pos(h)}</span></h3><p>League: ${esc(nice(h.division))}</p><p>Last season: ${esc(nice(h.lastSeasonPosition))}</p><p>Squad change: ${esc(fmtSigned(h.transferImpact))}</p><p>XI rating: ${esc(nice(h.xiRating||h.ratingPrior))}</p></div><div class="team-card"><h3>${esc(m.away)} <span class="rank">${pos(a)}</span></h3><p>League: ${esc(nice(a.division))}</p><p>Last season: ${esc(nice(a.lastSeasonPosition))}</p><p>Squad change: ${esc(fmtSigned(a.transferImpact))}</p><p>XI rating: ${esc(nice(a.xiRating||a.ratingPrior))}</p></div></div></div><div class="panel"><div class="ptitle">LINEUPS</div><div class="lineups">${lineup(h,m.home)}${lineup(a,m.away)}</div><div class="note">Source: ${esc(m.lineupSource||"not published")}. Sofascore is used for lineup/incident data; FotMob remains the match-detail fallback.</div></div><div class="panel"><div class="ptitle">GOALS & LIVE EVENTS</div>${scorerLine(m)||'<div class="note">No goals recorded yet.</div>'}</div></div></div>`}
function matchHTML(m){const r=m.model||{},open=openId===String(m.id);return `<article class="match ${st(m)==="LIVE"?"live":""}" id="m-${esc(m.id)}"><div class="match-head"><div>${matchTime(m)}</div><div class="teams"><span>${esc(m.home)}</span><span class="vs">vs</span><span>${esc(m.away)}</span></div><div class="score ${m.homeScore==null?"pending":""}">${score(m)}</div><div class="verdict ${isDraw(r.verdict)?"draw":""}">${esc(nice(r.verdict,"ANALYSIS PENDING"))}<span class="confidence">${Math.round(Number(r.confidence)||0)}/100</span></div><button class="analyze ${open?"open":""}" onclick="toggleAnalysis('${esc(m.id)}')">${open?"CLOSE":"ANALYZE"}</button></div>${scorerLine(m)}<div class="analysis ${open?"open":""}">${analysis(m)}</div></article>`}

function updateAutoStatus(ok=true){
  const el=$("#autoStatus");
  if(!el)return;
  if(!ok){el.textContent="AUTO · waiting";return}
  const now=new Date();
  el.textContent=`AUTO · ${now.toLocaleTimeString([],{
    hour:"2-digit",minute:"2-digit",second:"2-digit"
  })}`;
}

function render(){if(!DATA){$("#fixtures").innerHTML='<div class="empty">Loading FootballEdge…</div>';return}$("#updated").textContent=DATA.updated||new Date(DATA.updatedAt||Date.now()).toLocaleString();$("#feedStatus").textContent=`${DATA.fixtureCount||0} FIXTURES · LIVE FEED`;const live=(DATA.matches||[]).filter(m=>st(m)==="LIVE");$("#liveStrip").innerHTML=live.length?live.map(m=>`<div class="live-card"><div class="tag heartbeat"><i></i> LIVE · ${esc(m.competition)}</div><div class="pair">${esc(m.home)} vs ${esc(m.away)}</div><div class="live-score">${score(m)}</div><div class="min">${esc(m.minute?.short||"Live")}</div>${scorerLine(m)}</div>`).join(""):"";const comps=[...new Set((DATA.matches||[]).map(m=>m.competition).filter(Boolean))];$("#filters").innerHTML=`<button class="filter ${filter==="ALL"?"active":""}" onclick="setFilter('ALL')">ALL</button>`+comps.map(c=>`<button class="filter ${filter===c?"active":""}" onclick='setFilter(${JSON.stringify(c)})'>${esc(c)}</button>`).join("");const ms=(DATA.matches||[]).filter(m=>filter==="ALL"||m.competition===filter);const groups={};ms.forEach(m=>(groups[m.competition]??=[]).push(m));$("#fixtures").innerHTML=Object.entries(groups).map(([c,arr])=>`<section class="competition"><div class="comp-head"><span class="comp-logo">${esc((arr[0].competitionCode||c.slice(0,3)).toUpperCase())}</span><h2>${esc(c)}</h2><span class="count">${arr.length} MATCH${arr.length===1?"":"ES"}</span></div>${arr.map(matchHTML).join("")}</section>`).join("")}
function toggleAnalysis(id){openId=openId===String(id)?null:String(id);render();if(openId)requestAnimationFrame(()=>document.getElementById(`m-${CSS.escape(String(id))}`)?.scrollIntoView({behavior:"smooth",block:"nearest"}))}
function setFilter(x){filter=x;openId=null;render()}
async function loadStatic(){try{const r=await fetch(`${DATA_URL}?v=${Date.now()}`,{cache:"no-store"});if(!r.ok)throw Error(`HTTP ${r.status}`);DATA=await r.json();lastStaticUpdate=DATA.updatedAt;render();updateAutoStatus(true)}catch(e){if(!DATA)$("#fixtures").innerHTML=`<div class="error"><b>Football data feed unavailable.</b><br>${esc(e.message)}</div>`}}
async function pollLive(){
  if(!DATA)return;
  const candidates=(DATA.matches||[]).filter(m=>
    (st(m)==="LIVE" || st(m)==="FT") &&
    (!Array.isArray(m.scorers)||!m.scorers.length || st(m)==="LIVE")
  );
  if(!candidates.length)return;

  const dates=[...new Set(candidates.map(m=>{
    const d=new Date(m.kickoff||Date.now());
    return isNaN(d)?null:d.toISOString().slice(0,10);
  }).filter(Boolean))];

  const scheduleCache={};
  const norm=n=>String(n||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"")
    .replace(/[^a-z0-9]/g,"").replace(/footballclub|fc$/g,"");

  async function scheduled(date){
    if(scheduleCache[date])return scheduleCache[date];
    try{
      const r=await fetch(`https://www.sofascore.com/api/v1/sport/football/scheduled-events/${date}`,{cache:"no-store"});
      const j=r.ok?await r.json():{};
      return scheduleCache[date]=Array.isArray(j.events)?j.events:[];
    }catch(e){return scheduleCache[date]=[]}
  }

  async function findEvent(m){
    if(m.sofascoreEventId)return m.sofascoreEventId;
    const base=new Date(m.kickoff||Date.now());
    if(isNaN(base))return null;
    for(const off of [-1,0,1]){
      const d=new Date(base); d.setUTCDate(d.getUTCDate()+off);
      const day=d.toISOString().slice(0,10);
      const events=await scheduled(day);
      const hn=norm(m.home), an=norm(m.away);
      const hit=events.find(e=>{
        const h=norm(e?.homeTeam?.name), a=norm(e?.awayTeam?.name);
        return (h===hn&&a===an) || h.includes(hn)||hn.includes(h) ? (a.includes(an)||an.includes(a)) : false;
      });
      if(hit)return hit.id;
    }
    return null;
  }

  await Promise.all(candidates.map(async m=>{
    try{
      const sid=await findEvent(m);
      if(!sid)return;
      m.sofascoreEventId=sid;

      const requests=[fetch(`https://www.sofascore.com/api/v1/event/${sid}`,{cache:"no-store"})];
      if(st(m)==="LIVE" || !Array.isArray(m.scorers)||!m.scorers.length)
        requests.push(fetch(`https://www.sofascore.com/api/v1/event/${sid}/incidents`,{cache:"no-store"}));

      const res=await Promise.all(requests);
      const ev=res[0]?.ok?await res[0].json():null;
      const inc=res[1]?.ok?await res[1].json():null;

      if(ev?.event){
        m.homeScore=ev.event.homeScore?.current??m.homeScore;
        m.awayScore=ev.event.awayScore?.current??m.awayScore;
        if(ev.event.status?.type==="finished")m.status="FT";
        m.minute={short:ev.event.status?.description||ev.event.status?.type||"Live"};
      }
      if(inc?.incidents){
        m.scorers=inc.incidents.filter(x=>x.incidentType==="goal").map(x=>({
          minute:x.time,added:x.addedTime,team:x.isHome?"home":"away",
          scorer:x.player?.name,assist:x.assist1?.name||x.assist2?.name,
          ownGoal:x.incidentClass==="ownGoal"
        }));
      }
    }catch(e){}
  }));
  render();
}
loadStatic();setInterval(loadStatic,5000);setInterval(pollLive,5000);
window.toggleAnalysis=toggleAnalysis;window.setFilter=setFilter;
