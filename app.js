const DATA_URL="data/fixtures.json";
let DATA=null, filter="ALL", openId=null;

const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const num=(x)=>Number.isFinite(Number(x))?Number(x):null;
const nice=(x,fallback="Not available")=>{
  if(x===null||x===undefined||x===""||x==="—"||x==="--"||String(x).toLowerCase()==="none") return fallback;
  return String(x);
};
const pct=x=>`${Math.round((Number(x)||0)*100)}%`;
const verdictClass=v=>String(v||"").startsWith("DRAW")?"draw":"";
const cleanStatus=s=>String(s||"").toUpperCase();

function teamData(m,side){return side==="home"?(m.homeData||{}):(m.awayData||{});}
function formPills(form){
  const chars=String(form||"").replace(/[^WDL]/g,"").slice(-5).split("");
  return chars.length?chars.map(x=>`<span class="pill ${x}">${x}</span>`).join(""):`<span class="muted">Not available</span>`;
}
function formLabel(d){return d.formPoints!=null?`${nice(d.formPoints)}/15 pts`:"No recent-form sample";}
function position(d){return d.position!=null?`#${d.position}`:"Position unavailable";}
function score(m){
  const live=["LIVE","FT"].includes(cleanStatus(m.status));
  return live&&m.homeScore!=null&&m.awayScore!=null
    ? `${esc(m.homeScore)} : ${esc(m.awayScore)}` : "— : —";
}
function kickoff(m){
  if(cleanStatus(m.status)==="LIVE") return `<b class="time live">LIVE</b>`;
  if(cleanStatus(m.status)==="FT") return `<b class="time">FT</b>`;
  if(!m.kickoff) return `<span class="time">Time unavailable</span>`;
  try{return `<span class="time">${new Date(m.kickoff).toLocaleTimeString([], {hour:"numeric",minute:"2-digit"})}</span>`}
  catch{return `<span class="time">Upcoming</span>`}
}
function factorRows(m,r){
  const h=teamData(m,"home"),a=teamData(m,"away");
  const hp=num(h.position),ap=num(a.position);
  const fp=num(h.formPoints),fq=num(a.formPoints);
  const xh=num(h.xg),xa=num(a.xg);
  const factors=[
    ["Division / league strength", divisionSignal(h,a), "STRUCTURAL"],
    ["League position", hp&&ap?positionSignal(hp,ap):0, hp&&ap?`${hp} vs ${ap}`:"Unavailable"],
    ["Recent form", fp!=null&&fq!=null?clamp((fp-fq)*4,-20,20):0, fp!=null&&fq!=null?`${fp} vs ${fq}`:"Unavailable"],
    ["xG / attacking output", xh!=null&&xa!=null?clamp((xh-xa)*18,-18,18):0, xh!=null&&xa!=null?`${xh} vs ${xa}`:"Unavailable"],
    ["Home advantage", homeSignal(h,a), "Small context adjustment"],
    ["H2H", h2hSignal(m), m.h2hSummary?m.h2hSummary.replace("H2H summary ",""):"Unavailable"]
  ];
  return factors.map(([name,val,desc])=>{
    const v=Math.round(val||0), width=Math.min(100,Math.abs(v)*3);
    return `<div class="factor"><div class="name">${esc(name)}</div><div class="meter"><i style="width:${width}%"></i></div><div class="value">${v>0?"+":""}${v}</div></div>`;
  }).join("");
}
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
function divisionSignal(h,a){
  if(!h.division||!a.division)return 0;
  if(h.division===a.division)return 0;
  // Cross-division: never use raw position. Existing model verdict remains authoritative.
  return 0;
}
function positionSignal(h,a){return clamp((a-h)*1.8,-15,15)}
function homeSignal(){return 3}
function h2hSignal(m){
  const s=String(m.h2hSummary||"");
  const q=s.match(/(\d+)[–-](\d+)[–-](\d+)/);
  if(!q)return 0;
  return clamp((Number(q[1])-Number(q[3]))*1.5,-8,8);
}

function evidence(m,r){
  const h=teamData(m,"home"),a=teamData(m,"away");
  const items=[];
  if(h.division&&a.division){
    items.push(["D","Competition context",h.division===a.division?`${h.division} vs ${a.division}; league positions can be compared directly.`:`${h.division} vs ${a.division}; raw positions are not treated as equivalent across divisions.`]);
  }
  if(h.position!=null&&a.position!=null) items.push(["#","Table position",`${m.home} ${position(h)} · ${m.away} ${position(a)}.`]);
  if(h.formPoints!=null||a.formPoints!=null) items.push(["F","Recent form",`${m.home}: ${formLabel(h)} · ${m.away}: ${formLabel(a)}.`]);
  if(h.xg!=null||a.xg!=null) items.push(["xG","Expected goals",`${m.home}: ${nice(h.xg)} · ${m.away}: ${nice(a.xg)}.`]);
  if(m.h2hSummary&& !/not available/i.test(m.h2hSummary)) items.push(["H2H","Head-to-head",m.h2hSummary]);
  const hi=(h.injuries||[]).length, ai=(a.injuries||[]).length;
  if(hi||ai) items.push(["!","Availability",`${m.home}: ${hi} listed absence/availability entries · ${m.away}: ${ai}.`]);
  if(!items.length) items.push(["i","Data status","FotMob has not supplied enough secondary metrics for this fixture yet. The model does not invent them."]);
  return items.map(([ic,t,p])=>`<div class="evidence-item"><div class="icon">${esc(ic)}</div><div><b>${esc(t)}</b><p>${esc(p)}</p></div></div>`).join("");
}

function statRows(m){
  const h=teamData(m,"home"),a=teamData(m,"away");
  const rows=[
    ["League",nice(h.division),nice(a.division)],
    ["Position",position(h),position(a)],
    ["Form",nice(h.form,"Unavailable"),nice(a.form,"Unavailable")],
    ["Form points",formLabel(h),formLabel(a)],
    ["xG",nice(h.xg),nice(a.xg)],
    ["Squad availability",`${(h.injuries||[]).length} listed`,`${(a.injuries||[]).length} listed`]
  ];
  return rows.map(r=>`<div class="stat-row"><span class="home">${esc(r[1])}</span><label>${esc(r[0])}</label><span class="away">${esc(r[2])}</span></div>`).join("");
}

function lineupCard(d,name){
  const list=Array.isArray(d.lineup)?d.lineup:[];
  if(!list.length)return `<div class="lineup-card"><h4>${esc(name)}</h4><div class="empty-data">FotMob lineup not available yet. This is normal before confirmed XI.</div></div>`;
  return `<div class="lineup-card"><h4>${esc(name)} <span class="muted">· ${list.length} listed</span></h4>`+
    list.slice(0,18).map(p=>`<div class="player"><span>${esc(nice(p.position,""))} ${esc(nice(p.name,"Unknown player"))}</span><span class="rating">${p.rating!=null?esc(p.rating):""}</span></div>`).join("")+
    `</div>`;
}

function analysisHTML(m,r){
  const p=r.probabilities||[0,0,0];
  const h=teamData(m,"home"),a=teamData(m,"away");
  const verdict=nice(r.verdict,"MODEL UNAVAILABLE");
  const confidence=Math.round(num(r.confidence)||0);
  const projected=nice(r.projected,"Score unavailable");
  const completeness=Math.round(num(r.dataCompleteness)||0);
  return `<div class="analysis-shell">
    <div>
      <div class="panel">
        <div class="panel-title">MODEL DECISION</div>
        <div class="decision ${verdictClass(verdict)}">
          <div><div class="label">${verdictClass(verdict)?"DRAW":"BEST OUTCOME"}</div><div class="big">${esc(verdict)}</div><div class="sub">Confidence ${confidence}/100 · Based only on available FotMob evidence</div></div>
          <div class="projected"><small>PROJECTED SCORE</small><b>${esc(projected)}</b></div>
        </div>
        <div class="prob">
          <div class="prob-card"><div class="name">${esc(m.home)}</div><strong>${pct(p[0])}</strong><div class="bar"><i style="width:${Math.min(100,(p[0]||0)*100)}%"></i></div></div>
          <div class="prob-card"><div class="name">DRAW</div><strong>${pct(p[1])}</strong><div class="bar"><i style="width:${Math.min(100,(p[1]||0)*100)}%"></i></div></div>
          <div class="prob-card"><div class="name">${esc(m.away)}</div><strong>${pct(p[2])}</strong><div class="bar"><i style="width:${Math.min(100,(p[2]||0)*100)}%"></i></div></div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">KEY FACTORS</div>
        <div class="factors">${factorRows(m,r)}</div>
      </div>
      <div class="panel">
        <div class="panel-title">EVIDENCE</div>
        <div class="evidence">${evidence(m,r)}</div>
      </div>
    </div>
    <div>
      <div class="panel">
        <div class="panel-title">TEAM COMPARISON</div>
        <div class="team-grid">
          <div class="team-card"><div class="team-head"><b>${esc(m.home)}</b><span class="position">${esc(position(h))}</span></div><div class="stat-list">${statRows(m).split("</div>").slice(0,6).join("</div>")}</div>
          <div class="team-card"><div class="team-head"><b>${esc(m.away)}</b><span class="position">${esc(position(a))}</span></div><div class="stat-list">${statRows(m).split("</div>").slice(0,6).join("</div>")}</div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">RECENT FORM</div>
        <div class="form-row">
          <div class="form-team"><b>${esc(m.home)}</b><div class="form-pills">${formPills(h.form)}</div></div>
          <div class="form-team"><b>${esc(m.away)}</b><div class="form-pills">${formPills(a.form)}</div></div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">FOTMOB LINEUPS</div>
        <div class="lineup-grid">${lineupCard(h,m.home)}${lineupCard(a,m.away)}</div>
        <div class="footer-note">Lineups appear when FotMob publishes them. No RotoWire dependency.</div>
      </div>
      <div class="panel">
        <div class="panel-title">DATA QUALITY</div>
        <div class="stat-row"><span class="home">FotMob</span><label>Source</label><span class="away">Primary</span></div>
        <div class="stat-row"><span class="home">${completeness}%</span><label>Completeness</label><span class="away">${completeness>=80?"Strong":"Limited"}</span></div>
        <div class="footer-note">Missing data reduces confidence; it is never filled with invented numbers.</div>
      </div>
    </div>
  </div>`;
}

function matchHTML(m){
  const r=m.model||{verdict:"DRAW",confidence:0,probabilities:[.33,.34,.33],projected:"Unavailable"};
  const live=cleanStatus(m.status)==="LIVE";
  const open=openId===String(m.id);
  return `<article class="match ${live?"live":""}" id="m-${esc(m.id)}">
    <div class="row">
      <div>${kickoff(m)}</div>
      <div class="teams"><span>${esc(m.home)}</span><span class="vs">vs</span><span>${esc(m.away)}</span></div>
      <div class="score ${score(m).startsWith("—")?"pending":""}">${score(m)}</div>
      <div class="verdict ${verdictClass(r.verdict)}">${esc(nice(r.verdict,"ANALYSIS PENDING"))}<span class="confidence">${Math.round(num(r.confidence)||0)}/100 confidence</span></div>
      <button class="analyze ${open?"open":""}" onclick="toggleAnalysis('${esc(m.id)}')">${open?"CLOSE":"ANALYZE"}</button>
    </div>
    <div class="analysis ${open?"open":""}" id="a-${esc(m.id)}">${analysisHTML(m,r)}</div>
  </article>`;
}

function render(){
  if(!DATA){$("#fixtures").innerHTML='<div class="empty">No feed loaded.</div>';return}
  $("#updated").textContent=DATA.updatedAt?new Date(DATA.updatedAt).toLocaleString():"—";
  $("#feedStatus").textContent=`${DATA.fixtureCount||0} FIXTURES · FOTMOB`;
  const live=(DATA.matches||[]).filter(m=>cleanStatus(m.status)==="LIVE");
  $("#liveStrip").innerHTML=live.length?live.map(m=>`<div class="live-card"><div class="live-title">● LIVE · ${esc(m.competition)}</div><div class="teams">${esc(m.home)} vs ${esc(m.away)}</div><div class="score">${score(m)}</div><div class="minute">${esc(nice(m.minute,"Live"))}</div></div>`).join(""):"";
  const comps=[...new Set((DATA.matches||[]).map(m=>m.competition).filter(Boolean))];
  $("#filters").innerHTML=`<button class="${filter==="ALL"?"active":""}" onclick="setFilter('ALL')">ALL</button>`+
    comps.map(c=>`<button class="${filter===c?"active":""}" onclick='setFilter(${JSON.stringify(c)})'>${esc(c)}</button>`).join("");
  const matches=(DATA.matches||[]).filter(m=>filter==="ALL"||m.competition===filter);
  if(!matches.length){$("#fixtures").innerHTML='<div class="empty">No matches in this filter.</div>';return}
  const groups={};matches.forEach(m=>(groups[m.competition]??=[]).push(m));
  $("#fixtures").innerHTML=Object.entries(groups).map(([comp,arr])=>`<section class="league"><div class="league-head"><span class="badge">${esc((arr[0].competitionCode||comp.slice(0,2)).toUpperCase())}</span><h2>${esc(comp)}</h2><span class="count">${arr.length} MATCH${arr.length===1?"":"ES"}</span></div>${arr.map(matchHTML).join("")}</section>`).join("");
}
function toggleAnalysis(id){
  openId=openId===String(id)?null:String(id);
  render();
  if(openId){
    requestAnimationFrame(()=>document.getElementById(`m-${CSS.escape(String(id))}`)?.scrollIntoView({behavior:"smooth",block:"nearest"}));
  }
}
function setFilter(x){filter=x;openId=null;render()}
async function load(){
  try{
    const r=await fetch(`${DATA_URL}?t=${Date.now()}`,{cache:"no-store"});
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    DATA=await r.json();render();
  }catch(e){
    $("#feedStatus").textContent="FEED ERROR";
    $("#fixtures").innerHTML=`<div class="error"><b>Data feed unavailable.</b><br>${esc(e.message)}<br><br>Run the FootballEdge GitHub Action and check its log.</div>`;
  }
}
$("#refresh").onclick=load;
load();setInterval(load,60000);
