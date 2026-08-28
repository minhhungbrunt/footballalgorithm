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
    const og=g.ownGoal?" · OG":"", min=g.minute!=null?`${esc(g.minute)}'`:"";
    const ast=g.assist?` <small>🅰 ${esc(g.assist)}</small>`:"";
    const img=g.scorerImage||playerFace(g);
    return `<span class="goal-event" title="${esc(side)}">${img?`<img class="scorer-face" src="${esc(img)}" alt="" loading="lazy" onerror="this.style.display='none'">`:""}<span>⚽ ${esc(g.scorer||"Goal")} ${min}${og}${ast}</span></span>`;
  }).join("")}</div>`;
}

function lineup(d,name){
  const list=Array.isArray(d.lineup)?d.lineup:[],bench=Array.isArray(d.bench)?d.bench:[];
  if(!list.length)return `<div class="lineup"><h3>${esc(name)}</h3><div class="empty-data">Lineup not published yet.</div></div>`;
  const face=(p)=>playerFace(p);
  return `<div class="lineup"><h3>${esc(name)} <span class="rank">${d.lineupConfirmed?"CONFIRMED XI":"EXPECTED XI"}</span></h3>
    ${d.formation?`<div class="formation">${esc(d.formation)}</div>`:""}
    <div class="player-list">${list.slice(0,18).map(p=>`<div class="player">
      <span class="pos">${esc(nice(p.position,""))}</span>
      ${face(p)?`<img class="player-face" src="${esc(face(p))}" alt="" loading="lazy" onerror="this.style.display='none'">`:""}
      <span class="pname">${esc(nice(p.name,"Unknown"))}</span>
      <span class="rating">${p.rating!=null?esc(p.rating):""}</span>
    </div>`).join("")}</div>
    ${bench.length?`<div class="bench"><b>Bench</b> · ${bench.slice(0,9).map(p=>esc(p.name||"Unknown")).join(", ")}</div>`:""}
  </div>`;
}

function recentResults(d){const r=Array.isArray(d.recentResults)?d.recentResults:[];if(!r.length)return `<span class="note">No recent results returned</span>`;return `<div class="recent-results">${r.map(x=>`<div><i class="pill ${esc(x.result)}">${esc(x.result)}</i><span>${esc(x.opponent||"Opponent")}</span><b>${esc(x.gf)}-${esc(x.ga)}</b></div>`).join("")}</div>`}
function evidence(m){const h=td(m,"home"),a=td(m,"away"),items=[];if(h.division||a.division)items.push(["DIV","Current league",`${m.home}: ${nice(h.division)} · ${m.away}: ${nice(a.division)}. Cup competition does not determine domestic division.`]);if(h.position!=null||a.position!=null)items.push(["POS","Current table",`${m.home}: ${pos(h)} · ${m.away}: ${pos(a)}${h.division!==a.division?" · cross-division positions are not directly compared":""}.`]);if(h.lastSeasonPosition!=null||a.lastSeasonPosition!=null)items.push(["25/26","Last season",`${m.home}: ${nice(h.lastSeasonPosition)} · ${m.away}: ${nice(a.lastSeasonPosition)}. Important early-season prior.`]);if(h.form||a.form)items.push(["FORM","Recent form",`${m.home}: ${nice(h.form)} (${h.formPoints||0}/15) · ${m.away}: ${nice(a.form)} (${a.formPoints||0}/15).`]);if(h.xg!=null||a.xg!=null)items.push(["xG","Expected goals",`${m.home}: ${nice(h.xg)} · ${m.away}: ${nice(a.xg)}.`]);if(h.xiRating!=null||a.xiRating!=null)items.push(["XI","Starting XI",`${m.home}: ${nice(h.xiRating)} · ${m.away}: ${nice(a.xiRating)}.`]);if(h.transferImpact!=null||a.transferImpact!=null)items.push(["TR","Squad change",`${m.home}: ${fmtSigned(h.transferImpact)} · ${m.away}: ${fmtSigned(a.transferImpact)}.`]);if(m.h2hSummary&&!/not available/i.test(m.h2hSummary))items.push(["H2H","Head-to-head",m.h2hSummary]);if(!items.length)items.push(["i","Data status","Not enough secondary evidence returned yet."]);return items.map(x=>`<div class="evidence-item"><div class="eicon">${esc(x[0])}</div><div><b>${esc(x[1])}</b><p>${esc(x[2])}</p></div></div>`).join("")}
function factors(m){return (m.model?.factors||[]).map(x=>{const v=Number(x[1])||0,w=Math.min(100,Math.abs(v)*2.4);return `<div class="factor"><span class="factor-name">${esc(x[0])}</span><span class="meter"><i style="width:${w}%"></i></span><span class="factor-val">${v>0?"+":""}${v.toFixed(1)}</span></div>`}).join("")}
function probabilities(m){const p=m.model?.probabilities||[.33,.34,.33];return `<div class="probs"><div class="prob"><span>${esc(m.home)}</span><strong>${pct(p[0])}</strong><div class="bar"><i style="width:${p[0]*100}%"></i></div></div><div class="prob"><span>DRAW</span><strong>${pct(p[1])}</strong><div class="bar"><i style="width:${p[1]*100}%"></i></div></div><div class="prob"><span>${esc(m.away)}</span><strong>${pct(p[2])}</strong><div class="bar"><i style="width:${p[2]*100}%"></i></div></div></div>`}
function analysis(m){const r=m.model||{},h=td(m,"home"),a=td(m,"away"),note=resultNote(m);return `<div class="analysis-grid"><div><div class="panel"><div class="ptitle">MODEL DECISION</div><div class="decision ${isDraw(r.verdict)?"draw":""}"><div><div class="label">BEST OUTCOME</div><div class="big">${esc(nice(r.verdict,"MODEL PENDING"))}</div><div class="sub">Confidence ${esc(r.confidence??0)}/100 · ${esc(r.decisionNote||"")}</div></div><div class="projected"><small>PROJECTED SCORE</small><b>${esc(nice(r.projected))}</b></div></div>${probabilities(m)}${note?`<div class="post-note">${note}</div>`:""}</div><div class="panel"><div class="ptitle">MODEL FACTORS</div>${factors(m)}</div><div class="panel"><div class="ptitle">DEEP EVIDENCE</div>${evidence(m)}</div></div><div><div class="panel"><div class="ptitle">FORM & RESULTS</div><div class="form-box"><div class="form-team"><b>${esc(m.home)} ${formPills(h.form)}</b>${recentResults(h)}</div><div class="form-team"><b>${esc(m.away)} ${formPills(a.form)}</b>${recentResults(a)}</div></div></div><div class="panel"><div class="ptitle">TEAM SNAPSHOT</div><div class="team-compare"><div class="team-card"><h3>${esc(m.home)} <span class="rank">${pos(h)}</span></h3><p>League: ${esc(nice(h.division))}</p><p>Last season: ${esc(nice(h.lastSeasonPosition))}</p><p>Squad change: ${esc(fmtSigned(h.transferImpact))}</p><p>XI rating: ${esc(nice(h.xiRating||h.ratingPrior))}</p></div><div class="team-card"><h3>${esc(m.away)} <span class="rank">${pos(a)}</span></h3><p>League: ${esc(nice(a.division))}</p><p>Last season: ${esc(nice(a.lastSeasonPosition))}</p><p>Squad change: ${esc(fmtSigned(a.transferImpact))}</p><p>XI rating: ${esc(nice(a.xiRating||a.ratingPrior))}</p></div></div></div><div class="panel"><div class="ptitle">LINEUPS</div><div class="lineups">${lineup(h,m.home)}${lineup(a,m.away)}</div><div class="note">Source: ${esc(m.lineupSource||"not published")}. Sofascore is used for lineup/incident data; FotMob remains the match-detail fallback.</div></div><div class="panel"><div class="ptitle">GOALS & LIVE EVENTS</div>${scorerLine(m)||'<div class="note">No goals recorded yet.</div>'}</div></div></div>`}
function liveClockHTML(m){
  return `<span class="live-clock" data-live-match-id="${esc(m.id)}">${esc(liveElapsedLabel(m))}</span>`;
}
function matchHTML(m){
  const r=m.model||{},open=openId===String(m.id), live=st(m)==="LIVE";
  return `<article class="match ${live?"live":""}" id="m-${esc(m.id)}" data-live-match-id="${live?esc(m.id):""}">
    <div class="match-head">
      <div>${live?`<b class="time live"><span class="heartbeat"><i></i> LIVE</span> · ${liveClockHTML(m)}</b>`:matchTime(m)}</div>
      <div class="teams"><span>${esc(m.home)}</span><span class="vs">vs</span><span>${esc(m.away)}</span></div>
      <div class="score ${m.homeScore==null?"pending":""}">${score(m)}</div>
      <div class="verdict ${isDraw(r.verdict)?"draw":""}">${esc(nice(r.verdict,"ANALYSIS PENDING"))}<span class="confidence">${Math.round(Number(r.confidence)||0)}/100</span></div>
      <button class="analyze ${open?"open":""}" onclick="toggleAnalysis('${esc(m.id)}')">${open?"CLOSE":"ANALYZE"}</button>
    </div>
    ${scorerLine(m)}
    <div class="analysis ${open?"open":""}">${analysis(m)}</div>
  </article>`;
}

function updateAutoStatus(ok=true){
  const el=$("#autoStatus");
  if(!el)return;
  if(!ok){el.textContent="AUTO · waiting";return}
  const now=new Date();
  el.textContent=`AUTO · ${now.toLocaleTimeString([],{
    hour:"2-digit",minute:"2-digit",second:"2-digit"
  })}`;
}


function liveElapsedLabel(match){
  const live = match?.status || match?.state || {};
  if (match?.status?.finished || match?.finished || match?.isFinished) return "";
  let start = match?.startTime || match?.startTimestamp || match?.kickoff ||
              match?.matchTime || live?.startTime || live?.startTimestamp;
  let ms = null;
  if (typeof start === "number") ms = start > 1e12 ? start : start * 1000;
  else if (start) {
    const d = new Date(start);
    if (!Number.isNaN(d.getTime())) ms = d.getTime();
  }
  if (ms != null) {
    const sec = Math.max(0, Math.floor((Date.now()-ms)/1000));
    const mins = Math.floor(sec/60), secs = sec%60;
    return `${mins}:${String(secs).padStart(2,"0")}`;
  }
  const raw = match?.minute?.short ?? match?.minute ?? live?.minute ?? match?.elapsed ?? "";
  if (raw !== "") {
    const s=String(raw);
    const mmss=s.match(/(\d{1,3}):(\d{2})/);
    if(mmss)return `${parseInt(mmss[1],10)}:${mmss[2]}`;
    const min=s.match(/(\d{1,3})/);
    if(min)return `${parseInt(min[1],10)}:00`;
    return s;
  }
  return "LIVE";
}
function updateLiveClocks(){
  document.querySelectorAll("[data-live-match-id]").forEach(el=>{
    const m = (window.DATA?.matches || []).find(x=>String(x.id)===String(el.dataset.liveMatchId));
    if (!m) return;
    const clock = el.querySelector(".live-clock");
    if (clock) clock.textContent = liveElapsedLabel(m);
  });
}


function playerFace(p){
  if(!p)return "";
  if(p.image)return p.image;
  const id=p.playerId||p.scorerId||p.assistId;
  return id ? `https://images.fotmob.com/image_resources/playerimages/${id}.png` : "";
}
function scorerLine(e){
  if(!e||!e.scorer)return "";
  const assist=e.assist ? ` · assist ${e.assist}` : "";
  const minute=(e.minute!==undefined&&e.minute!==null&&e.minute!=="") ? `${e.minute}'` : "";
  return `${minute} ${e.scorer}${assist}`.trim();
}


function confidenceOf(m){return Number(m.model?.confidence)||0}
function drawOf(m){return Number(m.model?.probabilities?.[1])||0}
function dashboard(){
  const ms=DATA.matches||[], live=ms.filter(m=>st(m)==="LIVE"), analyzed=ms.filter(m=>m.model);
  const best=analyzed.slice().sort((x,y)=>confidenceOf(y)-confidenceOf(x))[0];
  const draw=analyzed.slice().sort((x,y)=>drawOf(y)-drawOf(x))[0];
  const total=ms.length;
  return `<div class="dash-grid">
    <div class="dash-card hero-card"><div class="dash-kicker">TODAY'S EDGE</div>
      <b>${total}</b><span>matches on the board</span>
      <div class="dash-mini">${live.length?`<strong>🔴 ${live.length} LIVE</strong>`:"No live matches right now"}</div>
    </div>
    <div class="dash-card"><div class="dash-kicker">BEST READ</div>
      ${best?`<b>${esc(best.model.verdict||"—")}</b><span>${esc(best.home)} vs ${esc(best.away)}</span><div class="dash-score">${confidenceOf(best)}/100 confidence</div>`:`<b>—</b><span>Analysis pending</span>`}
    </div>
    <div class="dash-card"><div class="dash-kicker">DRAW WATCH</div>
      ${draw?`<b>${pct(drawOf(draw))}</b><span>${esc(draw.home)} vs ${esc(draw.away)}</span><div class="dash-score">highest draw probability</div>`:`<b>—</b><span>Draw data pending</span>`}
    </div>
    <div class="dash-card"><div class="dash-kicker">MODEL MOOD</div>
      <b>${analyzed.filter(m=>isDraw(m.model?.verdict)).length}</b><span>draw calls today</span>
      <div class="dash-score">${analyzed.length?`${analyzed.length} analyzed`:"Waiting for data"}</div>
    </div>
  </div>`;
}
function filteredMatches(){
  const q=clean($("#matchSearch")?.value).toLowerCase();
  const mode=$("#sortMode")?.value||"time";
  let ms=(DATA.matches||[]).filter(m=>{
    const hay=`${m.home} ${m.away} ${m.competition} ${m.competitionCountry}`.toLowerCase();
    return (!q||hay.includes(q)) && (filter==="ALL"||m.competition===filter);
  });
  ms.sort((x,y)=>{
    if(mode==="confidence")return confidenceOf(y)-confidenceOf(x);
    if(mode==="draw")return drawOf(y)-drawOf(x);
    if(mode==="upset"){
      const px=x.model?.probabilities||[0,0,0],py=y.model?.probabilities||[0,0,0];
      return Math.max(...py)-Math.max(...px);
    }
    return new Date(x.kickoff||0)-new Date(y.kickoff||0);
  });
  return ms;
}
function bindToolbar(){
  const s=$("#matchSearch"), sort=$("#sortMode");
  if(s&&!s.dataset.bound){s.dataset.bound="1";s.addEventListener("input",render)}
  if(sort&&!sort.dataset.bound){sort.dataset.bound="1";sort.addEventListener("change",render)}
}

function aiSay(html){
  const box=$("#aiMessages");
  if(!box)return;
  box.insertAdjacentHTML("beforeend",`<div class="ai-msg bot">${html}</div>`);
  box.scrollTop=box.scrollHeight;
}
function aiUser(text){
  const box=$("#aiMessages");
  box.insertAdjacentHTML("beforeend",`<div class="ai-msg user">${esc(text)}</div>`);
  box.scrollTop=box.scrollHeight;
}
function aiPct(m,i){return Number(m?.model?.probabilities?.[i])||0}
function aiCard(m,tag){
  const p=m.model?.probabilities||[];
  return `<div class="ai-game" onclick="toggleAnalysis('${esc(m.id)}')">
    <div><b>${esc(m.home)} vs ${esc(m.away)}</b><small>${esc(m.competition||"Football")} · ${esc(matchTime(m))}</small></div>
    <strong>${esc(m.model?.verdict||"—")}</strong>
    <span>H ${pct(aiPct(m,0))} · D ${pct(aiPct(m,1))} · A ${pct(aiPct(m,2))}</span>
    ${tag?`<em>${esc(tag)}</em>`:""}
  </div>`;
}
function footballAI(q){
  const all=DATA?.matches||[];
  const s=String(q||"").toLowerCase().trim();
  if(!all.length)return "I don't have any fixtures loaded yet. Once the feed updates, ask me again.";
  let ms=all.filter(m=>`${m.home} ${m.away} ${m.competition} ${m.competitionCountry}`.toLowerCase().includes(s));
  if(ms.length){
    const m=ms[0], p=m.model?.probabilities||[];
    return `<b>${esc(m.home)} vs ${esc(m.away)}</b><br><small>${esc(m.competition||"")}</small><div class="ai-result-pills">HOME ${pct(p[0]||0)} · DRAW ${pct(p[1]||0)} · AWAY ${pct(p[2]||0)}</div>${m.model?.verdict?`FootballEdge leans <b>${esc(m.model.verdict)}</b> with ${confidenceOf(m)}/100 confidence.`:"Analysis isn't available yet."}${m.scorers?.length?`<br><br>⚽ ${m.scorers.slice(0,3).map(g=>`${esc(g.scorer||"Goal")} ${g.minute!=null?g.minute+"'":""}`).join(" · ")}`:""}<br><br><span class="ai-hint">Click the game card in the match list to open the full analysis.</span>`;
  }
  let ranked;
  if(/\b(draw|tie)\b/.test(s)){
    ranked=all.filter(m=>m.model).sort((x,y)=>aiPct(y,1)-aiPct(x,1)).slice(0,3);
    return ranked.length?`🤝 <b>Draw Watch</b><br>These have the highest draw probabilities right now:${ranked.map(m=>aiCard(m,"DRAW WATCH")).join("")}`:"I don't have enough analyzed games for Draw Watch yet.";
  }
  if(/\b(upset|underdog)\b/.test(s)){
    ranked=all.filter(m=>m.model).map(m=>({m, u:Math.min(aiPct(m,0),aiPct(m,2))})).sort((x,y)=>y.u-x.u).slice(0,3).map(x=>x.m);
    return ranked.length?`🚨 <b>Upset Watch</b><br>These are the closest games where the underdog has a meaningful chance:${ranked.map(m=>aiCard(m,"UPSET WATCH")).join("")}`:"I don't have enough analyzed games for Upset Watch yet.";
  }
  ranked=all.filter(m=>m.model).sort((x,y)=>confidenceOf(y)-confidenceOf(x)).slice(0,3);
  if(/\b(best|watch|today|games|game)\b/.test(s)){
    return ranked.length?`🔥 <b>Best games to start with</b><br>I’m ranking these from the FootballEdge data currently loaded:${ranked.map(m=>aiCard(m,`${confidenceOf(m)}/100 confidence`)).join("")}`:"No analyzed games are loaded yet.";
  }
  if(/\b(confidence|sure|confident)\b/.test(s)){
    const m=ranked[0];
    return m?`The strongest current read is <b>${esc(m.home)} vs ${esc(m.away)}</b> at <b>${confidenceOf(m)}/100</b> confidence. That doesn't mean it's guaranteed — it means the model has the clearest edge among the loaded games.`:"No confidence data is loaded yet.";
  }
  return `I can search the games currently loaded on FootballEdge. Try:<br>• “best games today”<br>• “likely draws”<br>• “biggest upsets”<br>• “which game has the highest confidence?”<br>• or type a team name.`;
}
function askAI(q){
  q=String(q||"").trim(); if(!q)return;
  aiUser(q);
  const box=$("#aiMessages");
  box.insertAdjacentHTML("beforeend",`<div class="ai-msg bot typing">Thinking…</div>`);
  setTimeout(()=>{const t=box.querySelector(".typing");if(t)t.remove();aiSay(footballAI(q));},180);
  const inp=$("#aiPrompt"); if(inp){inp.value="";inp.focus();}
}
function toggleAIChat(){
  const el=$("#aiChat"); if(el)el.classList.toggle("collapsed");
}

function render(){
  if(!DATA){$("#fixtures").innerHTML='<div class="empty">Loading FootballEdge…</div>';return}
  $("#updated").textContent=DATA.updated||new Date(DATA.updatedAt||Date.now()).toLocaleString();
  $("#feedStatus").textContent=`${DATA.fixtureCount||0} FIXTURES · LIVE FEED`;
  $("#dashboard").innerHTML=dashboard();

  const live=(DATA.matches||[]).filter(m=>st(m)==="LIVE");
  $("#liveStrip").innerHTML=live.length?live.map(m=>`<button class="live-card live-match-link" data-live-match-id="${esc(m.id)}" onclick="toggleAnalysis('${esc(m.id)}')">
    <div class="tag heartbeat"><i></i> LIVE · ${esc(m.competition)}</div>
    <div class="pair">${esc(m.home)} <span>vs</span> ${esc(m.away)}</div>
    <div class="live-score">${score(m)}</div>
    <div class="min">${liveClockHTML(m)}</div>${scorerLine(m)}
  </button>`).join(""):"";

  const comps=[...new Set((DATA.matches||[]).map(m=>m.competition).filter(Boolean))].sort();
  $("#filters").innerHTML=`<button class="filter ${filter==="ALL"?"active":""}" onclick="setFilter('ALL')">ALL</button>`+
    comps.map(c=>`<button class="filter ${filter===c?"active":""}" onclick='setFilter(${JSON.stringify(c)})'>${esc(c)}</button>`).join("");

  bindToolbar();
  const ms=filteredMatches(), groups={};
  ms.forEach(m=>(groups[m.competition]??=[]).push(m));
  $("#fixtures").innerHTML=Object.entries(groups).map(([c,arr])=>{
    const country=arr[0].competitionCountry||"International";
    const flag=arr[0].competitionFlag||"⚽";
    return `<section class="competition"><div class="comp-head"><span class="comp-logo flag">${esc(flag)}</span>
      <div class="comp-title"><h2>${esc(c)}</h2><span class="country-label">${esc(country)}</span></div>
      <span class="count">${arr.length} MATCH${arr.length===1?"":"ES"}</span></div>
      ${arr.map(matchHTML).join("")}</section>`;
  }).join("") || '<div class="empty">No matches match your search.</div>';
  updateLiveClocks();
}

function toggleAnalysis(id){openId=openId===String(id)?null:String(id);render();if(openId)requestAnimationFrame(()=>document.getElementById(`m-${CSS.escape(String(id))}`)?.scrollIntoView({behavior:"smooth",block:"nearest"}))}
function setFilter(x){filter=x;openId=null;render()}
async function loadStatic(){try{const r=await fetch(`${DATA_URL}?v=${Date.now()}`,{cache:"no-store"});if(!r.ok)throw Error(`HTTP ${r.status}`);DATA=await r.json();window.DATA=DATA;lastStaticUpdate=DATA.updatedAt;render();updateAutoStatus(true)}catch(e){if(!DATA)$("#fixtures").innerHTML=`<div class="error"><b>Football data feed unavailable.</b><br>${esc(e.message)}</div>`}}
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

setInterval(updateLiveClocks,1000);

document.addEventListener("click",e=>{
  const card=e.target.closest(".live-match-link");
  if(!card)return;
  const id=card.dataset.liveMatchId;
  if(id && e.target.tagName!=="BUTTON") toggleAnalysis(id);
});
