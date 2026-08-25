const DATA_URL="data/fixtures.json";
let DATA=null, filter="ALL";

const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

function pct(x){return `${Math.round((Number(x)||0)*100)}%`}
function verdictClass(v){return String(v).startsWith("DRAW")?"draw":""}

function render(){
  if(!DATA){$("#fixtures").innerHTML='<div class="empty">No feed loaded.</div>';return}
  $("#updated").textContent=DATA.updatedAt?new Date(DATA.updatedAt).toLocaleString():"—";
  $("#feedStatus").textContent=`${DATA.fixtureCount||0} FIXTURES · ${DATA.sourceStatus||"FEED"}`;
  const live=(DATA.matches||[]).filter(m=>m.status==="LIVE");
  $("#liveStrip").innerHTML=live.length?live.map(m=>`<div class="live-card"><small>LIVE · ${esc(m.competition)}</small><b>${esc(m.home)} — ${esc(m.away)}</b><div class="score">${esc(m.homeScore??"—")} : ${esc(m.awayScore??"—")}</div><small>${esc(m.minute||"Live")}</small></div>`).join(""):"<div class='empty' style='padding:12px'>No live matches right now.</div>";

  const comps=[...new Set((DATA.matches||[]).map(m=>m.competition))];
  $("#filters").innerHTML=`<button class="${filter==="ALL"?"active":""}" onclick="setFilter('ALL')">ALL</button>`+
    comps.map(c=>`<button class="${filter===c?"active":""}" onclick='setFilter(${JSON.stringify(c)})'>${esc(c)}</button>`).join("");

  const matches=(DATA.matches||[]).filter(m=>filter==="ALL"||m.competition===filter);
  if(!matches.length){$("#fixtures").innerHTML='<div class="empty">No matches in this filter.</div>';return}
  const groups={};matches.forEach(m=>(groups[m.competition]??=[]).push(m));
  $("#fixtures").innerHTML=Object.entries(groups).map(([comp,arr])=>`
    <section class="league"><div class="league-head"><span class="badge">${esc((arr[0].competitionCode||comp.slice(0,2)).toUpperCase())}</span><h2>${esc(comp)}</h2><span class="count">${arr.length} MATCH${arr.length===1?"":"ES"}</span></div>
    ${arr.map(matchHTML).join("")}</section>`).join("");
}
function matchHTML(m){
  const r=m.model||fallbackModel(m), live=m.status==="LIVE";
  const score=m.status==="FT"||live?`${esc(m.homeScore??"—")} : ${esc(m.awayScore??"—")}`:"— : —";
  return `<article class="match ${live?"live":""}" id="m-${m.id}">
    <div class="row">
      <div class="time">${live?'<b style="color:var(--green)">LIVE</b>':esc(m.status==="FT"?"FT":m.kickoff||"—")}</div>
      <div class="teams"><span>${esc(m.home)}</span><span class="vs">vs</span><span>${esc(m.away)}</span></div>
      <div class="score">${score}</div>
      <div class="verdict ${verdictClass(r.verdict)}">${esc(r.verdict)}<span class="confidence">${Math.round(r.confidence)}/100 confidence</span></div>
      <button class="analyze" onclick="toggleAnalysis('${m.id}')">ANALYZE</button>
    </div>
    <div class="analysis" id="a-${m.id}">${analysisHTML(m,r)}</div>
  </article>`;
}
function fallbackModel(m){
  // Only a safety fallback for old/corrupt cached fixtures. It is deliberately neutral.
  return {verdict:"DRAW",confidence:45,probabilities:[.33,.34,.33],projected:"1–1",
    reasons:["Model data is incomplete for this match.","Refresh the GitHub data feed before relying on this fixture."]};
}
function analysisHTML(m,r){
  const p=r.probabilities||[0,0,0];
  const h=m.homeData||{},a=m.awayData||{};
  const reasons=(r.reasons||[]).map(x=>`<p>• ${esc(x)}</p>`).join("");
  const lineup=(team,name)=>`<div><h3>${esc(name)}</h3>${(team.lineup||[]).length?(team.lineup.map(x=>`<div class="player"><small>${esc(x.position||"")}</small>${esc(x.name)}${x.rating?` · ${esc(x.rating)}`:""}</div>`).join(""):"<span class='data-note'>RotoWire lineup not posted yet.</span>"}${(team.rotowireInjuries||team.injuries||[]).map(x=>`<div class="player inj">⚠ ${esc(x.name)} — ${esc(x.status||"OUT")}</div>`).join("")}</div>`;
  return `<div class="analysis-grid">
    <div class="box">
      <div class="decision ${verdictClass(r.verdict)}"><h3>MODEL VERDICT</h3><div class="big">${esc(r.verdict)}</div><div>Confidence ${Math.round(r.confidence)}/100 · Projected ${esc(r.projected||"—")}</div></div>
      <div class="prob"><div><b>${esc(m.home)}</b><strong>${pct(p[0])}</strong></div><div><b>DRAW</b><strong>${pct(p[1])}</strong></div><div><b>${esc(m.away)}</b><strong>${pct(p[2])}</strong></div></div>
    </div>
    <div class="box reason"><h3>DEEP EVIDENCE</h3>${reasons}<div class="data-note">Data completeness ${Math.round(r.dataCompleteness||0)}%. Missing fields reduce confidence; nothing is invented.</div></div>
    <div class="box"><h3>LEAGUE / FORM</h3>
      <p><b>${esc(m.home)}</b> — ${esc(h.division||"division unavailable")} · position ${esc(h.position??"—")} · form ${esc(h.form||"—")} · ${esc(h.formPoints??"—")}/15 pts</p>
      <p><b>${esc(m.away)}</b> — ${esc(a.division||"division unavailable")} · position ${esc(a.position??"—")} · form ${esc(a.form||"—")} · ${esc(a.formPoints??"—")}/15 pts</p>
      <p>xG: ${esc(h.xg??"—")} vs ${esc(a.xg??"—")} · H2H: ${esc(m.h2hSummary||"—")}</p>
    </div>
    <div class="box"><h3>ROTIWIRE LINEUP LISTING</h3><p><a class="rotowire" target="_blank" rel="noopener" href="${esc(m.rotowireUrl||"https://www.rotowire.com/soccer/lineups.php")}">Open RotoWire listing →</a></p><div class="lineups">${lineup(h,m.home)}${lineup(a,m.away)}</div></div>
  </div>`;
}
function toggleAnalysis(id){const x=$(`#a-${id}`);x.classList.toggle("open");if(x.classList.contains("open"))x.scrollIntoView({behavior:"smooth",block:"nearest"})}
function setFilter(x){filter=x;render()}
$("#refresh").onclick=load;
async function load(){
  try{
    const r=await fetch(`${DATA_URL}?t=${Date.now()}`,{cache:"no-store"});
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    DATA=await r.json();render();
  }catch(e){$("#feedStatus").textContent="FEED ERROR";$("#fixtures").innerHTML=`<div class="error"><b>Data feed unavailable.</b><br>${esc(e.message)}<br><br>Run the GitHub Action once and check its log. The site never fabricates fixtures.</div>`}
}
load();setInterval(load,60000);
