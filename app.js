const App=(()=>{
  const state={matches:[],league:"ALL",sort:"time",query:"",open:null};
  const $=id=>document.getElementById(id);
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const pct=n=>n==null?"—":Math.round(Number(n)*100)+"%";
  const leagues=["ALL","Premier League","Championship","League One","League Two","LaLiga","LaLiga 2","Copa del Rey","Bundesliga","2. Bundesliga","DFB Pokal","Serie A","Serie B","Coppa Italia","Ligue 1","Ligue 2","Coupe de France","Eredivisie","Eerste Divisie","Primeira Liga","Liga Portugal 2","FA Cup","EFL Cup","UEFA Champions League","UEFA Champions League Qualification","UEFA Europa League","UEFA Europa League Qualification","UEFA Conference League","UEFA Conference League Qualification","Scottish Premiership","Belgian Pro League","Turkish Super Lig","Saudi Pro League","MLS","Brasileirao","Liga MX"];

  async function init(){
    bind();buildTabs();await load();
    // Keep the page fresh without making the user reload. GitHub Actions is the
    // source refresh; this picks up the latest committed JSON automatically.
    setInterval(load,60000);
  }
  async function load(){
    try{
      const r=await fetch("data/fixtures.json?"+Date.now(),{cache:"no-store"});
      if(!r.ok)throw Error(r.status);
      const d=await r.json();state.matches=d.matches||[];
      $("updatedAt").textContent=d.updated||"—";$("fixtureCount").textContent=state.matches.length+" fixtures";
      $("dataStatus").innerHTML=`<i></i> ${d.source||"Football data"}`;$("dataStatus").className="status-dot live";
      render();
    }catch(e){
      $("dataStatus").innerHTML="<i></i> Feed unavailable";$("dataStatus").className="status-dot";
      $("updatedAt").textContent="Waiting for feed";$("fixtureCount").textContent="— fixtures";
      render();
    }
  }
  function bind(){
    $("refreshBtn").onclick=load;
    $("searchInput").oninput=e=>{state.query=e.target.value.toLowerCase();render()};
    document.querySelectorAll('.sort-btn').forEach(b=>b.onclick=()=>{document.querySelectorAll('.sort-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.sort=b.dataset.sort;render()});
  }
  function buildTabs(){
    $("leagueTabs").innerHTML=leagues.map(l=>`<button class="tab ${l==='ALL'?'active':''}" data-league="${esc(l)}">${esc(l)}</button>`).join('');
    document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.league=b.dataset.league;render()});
  }
  function filtered(){
    let a=state.matches.filter(m=>state.league==='ALL'||m.competition===state.league);
    if(state.query)a=a.filter(m=>(m.home+' '+m.away+' '+m.competition).toLowerCase().includes(state.query));
    if(state.sort==='model')a.sort((x,y)=>(y.model?.confidence||0)-(x.model?.confidence||0));
    else a.sort((x,y)=>timeValue(x)-timeValue(y));
    return a;
  }
  function timeValue(m){const d=Date.parse(m.time||'');return isNaN(d)?999999999999:d}
  function render(){
    const a=filtered();renderFeatured(a);renderLive(a);$("matchday").innerHTML='';
    if(!a.length){$("matchday").innerHTML='<div class="empty"><b>No fixtures loaded yet.</b><br><br>The scheduled GitHub Action fetches the daily feed. If FotMob is unavailable, the updater uses the live-score fallback and keeps the last good dataset instead of showing fake matches.</div>';return}
    const groups={};a.forEach(m=>(groups[m.competition]??=[]).push(m));
    Object.entries(groups).forEach(([league,g])=>{
      const block=document.createElement('section');block.className='league-block';
      block.innerHTML=`<div class="league-head"><div class="league-title"><div class="league-badge">${leagueIcon(league)}</div><h2>${esc(league)}</h2><span>${g.length} MATCH${g.length===1?'':'ES'}</span></div></div><div class="league-games"></div>`;
      const list=block.querySelector('.league-games');g.forEach(m=>list.appendChild(row(m)));$("matchday").appendChild(block);
    });
  }
  function leagueIcon(l){return ({'Premier League':'PL','LaLiga':'LL','Bundesliga':'BL','Serie A':'SA','Ligue 1':'L1','Eredivisie':'ER','Primeira Liga':'PT','UEFA Champions League':'UCL','UEFA Champions League Qualification':'UCL Q','UEFA Europa League':'UEL','UEFA Europa League Qualification':'UEL Q','UEFA Conference League':'UECL','UEFA Conference League Qualification':'UECL Q','EFL Cup':'EFL'}[l]||'FC')}
  function displayTime(m){
    if(m.status==='live')return `LIVE ${m.score!=null?m.score:''}`.trim();
    if(m.status==='finished')return `FT ${m.score!=null?m.score:''}`.trim();
    if(!m.time)return 'TBD';const d=Date.parse(m.time);return isNaN(d)?m.time:new Intl.DateTimeFormat(undefined,{hour:'numeric',minute:'2-digit'}).format(d);
  }
  function liveClass(m){return m.status==='live'?' live':m.status==='finished'?' finished':''}
  function row(m){
    const el=document.createElement('article');el.className='match-row'+liveClass(m)+(state.open===String(m.id)?' expanded':'');el.id='match-'+m.id;
    const model=m.model||fallbackModel(m);
    el.innerHTML=`<div class="match-time ${m.status==='live'?'live':''}">${esc(displayTime(m))}</div>
      <div class="teams"><span class="team-home">${esc(m.home)}</span><span class="dash">${m.status==='live'||m.status==='finished'?'':'vs'}</span><span class="team-away">${esc(m.away)}</span></div>
      ${m.status==='live'||m.status==='finished'?`<div class="score-pill">${esc(m.score||'—')}</div>`:''}
      <div class="positions">${m.homePos?`<b>#${esc(m.homePos)}</b>`:'—'} <span>·</span> ${m.awayPos?`<b>#${esc(m.awayPos)}</b>`:'—'}</div>
      <div class="mini-verdict"><strong>${esc(model.best||'—')}</strong><span>${esc(model.confidence||'—')}/100</span></div>
      <button class="analyze-btn">${state.open===String(m.id)?'CLOSE':'ANALYZE'}</button>
      <div class="analysis-panel">${analysis(m)}</div>`;
    el.querySelector('.analyze-btn').onclick=()=>{const id=String(m.id);state.open=state.open===id?null:id;render();if(state.open===id)setTimeout(()=>document.getElementById('match-'+id)?.scrollIntoView({behavior:'smooth',block:'nearest'}),30)};
    return el;
  }
  function fallbackModel(m){
    const h=Number(m.homeStrength||1500),a=Number(m.awayStrength||1500);const diff=h+10-a;
    const home=1/(1+Math.pow(10,-diff/400)),away=1-home;const draw=Math.min(.32,Math.max(.20,.29-Math.abs(diff)/3000));const scale=1-draw;
    return {home:home*scale,draw,away:away*scale,best:home>away?'WIN: '+m.home:'WIN: '+m.away,confidence:Math.round(45+Math.abs(home-away)*55),score:'—',dataCompleteness:0};
  }
  function money(v){if(v==null)return '—';v=Number(v);if(!isFinite(v))return '—';if(v>=100000000)return '€'+(v/1e6).toFixed(0)+'M';if(v>=1000000)return '€'+(v/1e6).toFixed(1)+'M';if(v>=1000)return '€'+Math.round(v/1000)+'K';return '€'+Math.round(v)}
  function rwPlayers(m,side){return m.rotowire?.[side]?.players||[]}
  function playerList(m,side){
    const ps=rwPlayers(m,side);if(!ps.length)return `<div class="lineup-empty">RotoWire listing not available for this competition yet.</div>`;
    const status=m.rotowire?.[side]?.status||'Predicted';
    return `<div class="lineup-status"><b>RotoWire ${esc(status)}</b><span>XI LISTING</span></div><div class="player-list">${ps.slice(0,11).map((p,i)=>`<div class="player-row"><span class="player-pos">${esc(p.position||'')}</span><span class="player-name">${esc(p.name||'—')}</span></div>`).join('')}</div>`;
  }
  function injuries(m,side){
    const rw=(m.rotowire?.[side]?.injuries)||[];const fot=(m.detail?.injuries||[]).filter(x=>x.team===(side==='home'?m.home:m.away));const arr=rw.length?rw:fot;
    if(!arr.length)return '<span class="ok">No reported absences in available source</span>';
    return arr.map(x=>`<span class="injury"><b>${esc(x.name||'Unknown')}</b> ${esc(x.reason||x.status||'OUT')}</span>`).join('');
  }
  function evidenceNarrative(m,x,d){
    const hf=m.homeForm||{},af=m.awayForm||{};const parts=[];
    if(m.homeLeague&&m.awayLeague&&m.homeLeague!==m.awayLeague)parts.push(`${m.home} are in ${m.homeLeague}, while ${m.away} are in ${m.awayLeague}; the model therefore gives division strength much more weight than venue.`);
    else if(m.homeLeague)parts.push(`Both teams are evaluated within ${m.homeLeague}, so table position and recent form are comparable.`);
    if(hf.sample||af.sample)parts.push(`Recent form: ${m.home} ${hf.last5||'—'} (${hf.points??'—'} points from ${hf.sample||0}) versus ${m.away} ${af.last5||'—'} (${af.points??'—'} points from ${af.sample||0}).`);
    if(d.homeLineupRating!=null||d.awayLineupRating!=null)parts.push(`FotMob player data gives available XI rating averages of ${d.homeLineupRating??'—'} and ${d.awayLineupRating??'—'}; these are supporting evidence, not a standalone pick.`);
    if(m.rotowire)parts.push(`RotoWire is used as the lineup/news cross-check; ${m.rotowire.home?.status||'predicted'} for ${m.home} and ${m.rotowire.away?.status||'predicted'} for ${m.away}.`);
    if(d.h2hHomeWins!=null)parts.push(`H2H sample: ${d.h2hHomeWins} ${m.home} wins, ${d.h2hDraws||0} draws, ${d.h2hAwayWins||0} ${m.away} wins.`);
    if(x.expectedGoals)parts.push(`Model expected goals: ${x.expectedGoals[0]} for ${m.home} and ${x.expectedGoals[1]} for ${m.away}.`);
    return parts.length?parts.map(p=>`<p>${esc(p)}</p>`).join(''):'<p>Evidence is still being collected. The model will not invent missing inputs.</p>';
  }
  function analysis(m){
    const x=m.model||fallbackModel(m),d=m.detail||{};const hL=m.homeLeague||x.homeLeague||'Unavailable',aL=m.awayLeague||x.awayLeague||'Unavailable';const rwLink=m.rotowire?.url;
    return `<div class="analysis-grid">
      <div class="analysis-card decision-card"><h3>MODEL VERDICT</h3><div class="decision"><div class="decision-title">CALCULATED BEST PLAY</div><div class="decision-value">${esc(x.best)}</div><div class="confidence">Confidence ${esc(x.confidence)}/100</div><div class="score">Projected ${esc(x.score||'—')}</div></div><div class="news-line"><b>${esc(m.competition)}</b> · ${esc(hL)} vs ${esc(aL)} · table ${m.homePos||'—'} vs ${m.awayPos||'—'}</div></div>
      <div class="analysis-card"><h3>PROBABILITIES & LIVE DATA</h3><div class="probs"><div class="prob"><small>${esc(m.home)}</small><b>${pct(x.home)}</b></div><div class="prob"><small>Draw</small><b>${pct(x.draw)}</b></div><div class="prob"><small>${esc(m.away)}</small><b>${pct(x.away)}</b></div></div><div class="evidence-grid"><div><b>Score</b><span>${esc(m.score||'Not live')}</span></div><div><b>xG</b><span>${x.expectedGoals?x.expectedGoals[0]+' – '+x.expectedGoals[1]:'Unavailable pre-match'}</span></div><div><b>Evidence coverage</b><span>${esc(x.dataCompleteness??0)}/8 blocks</span></div></div></div>
      <div class="analysis-card"><h3>DEEP EVIDENCE</h3><div class="deep-grid">${evidenceNarrative(m,x,d)}</div></div>
      <div class="analysis-card lineup-card"><div class="lineup-head"><h3>${esc(m.home)} · RotoWire</h3>${rwLink?'<a href="'+esc(rwLink)+'" target="_blank" rel="noopener">OPEN LISTING</a>':''}</div>${playerList(m,'home')}<div class="absence-box"><b>Availability</b>${injuries(m,'home')}</div></div>
      <div class="analysis-card lineup-card"><div class="lineup-head"><h3>${esc(m.away)} · RotoWire</h3>${rwLink?'<a href="'+esc(rwLink)+'" target="_blank" rel="noopener">OPEN LISTING</a>':''}</div>${playerList(m,'away')}<div class="absence-box"><b>Availability</b>${injuries(m,'away')}</div></div>
      <div class="analysis-card"><h3>MODEL REASONING</h3><div class="reasoning"><p>The verdict is based on team-strength priors, current domestic division, table position, recent results, lineup/player evidence, availability and H2H when those inputs exist.</p><p>Home advantage is intentionally a small adjustment and is reduced further for cross-division cup ties.</p><p>No bookmaker or Kalshi odds are used.</p></div></div>
    </div>`;
  }
  function renderFeatured(a){
    const m=a[0];if(!m){$('featuredContent').innerHTML='<div class="empty">No featured match.</div>';return}const x=m.model||fallbackModel(m);
    $('featuredContent').innerHTML=`<div class="featured-match"><div class="featured-team"><div class="name">${esc(m.home)}</div><div class="pos">${esc(m.homeLeague||'Division unavailable')}${m.homePos?' · #'+esc(m.homePos):''}</div></div><div class="featured-vs"><div class="time">${esc(displayTime(m))}</div><div class="vs">${m.score?esc(m.score)+' · ':''}${esc(m.competition)}</div></div><div class="featured-team"><div class="name">${esc(m.away)}</div><div class="pos">${esc(m.awayLeague||'Division unavailable')}${m.awayPos?' · #'+esc(m.awayPos):''}</div></div></div><div class="verdict"><span class="verdict-label">CALCULATED VERDICT</span><span class="verdict-main">${esc(x.best)}</span><span class="verdict-meta">${esc(x.confidence)}/100 · projected ${esc(x.score||'—')}</span></div>`;
  }
  function renderLive(a){
    const live=a.filter(m=>m.status==='live'||m.status==='finished').slice(0,12);const box=$("liveScores");
    if(!live.length){box.innerHTML='<span class="live-empty">No live matches right now</span>';return}
    box.innerHTML=live.map(m=>`<div class="live-card ${m.status==='live'?'on':''}"><span>${m.status==='live'?'LIVE':'FT'}</span><b>${esc(m.home)}</b><strong>${esc(m.score||'—')}</strong><b>${esc(m.away)}</b></div>`).join('');
  }
  return {init};
})();
App.init();


// ===== FOOTBALL EDGE V6 MODEL =====
// Deterministic, match-specific 1X2 model. No generic/home-default verdicts.
// Draw is a first-class outcome. Missing data reduces confidence rather than
// inventing evidence.

const MODEL={
  leagueStrength:{
    "Premier League":1880,"LaLiga":1860,"Bundesliga":1855,"Serie A":1845,"Ligue 1":1805,
    "Champions League":1880,"UEFA Champions League":1880,"UEFA Champions League Qualification":1815,
    "Europa League":1775,"Conference League":1715,
    "Championship":1645,"League One":1405,"League Two":1260,
    "LaLiga 2":1450,"2. Bundesliga":1480,"Serie B":1465,"Ligue 2":1435,
    "Eredivisie":1685,"Primeira Liga":1695,"Belgian Pro League":1615,
    "Scottish Premiership":1585,"Turkish Super Lig":1630,"Saudi Pro League":1610,
    "MLS":1560,"Brasileirao":1650,"Liga MX":1605
  },
  aliases:{
    "EFL Cup":"EFL Cup","Carabao Cup":"EFL Cup","FA Cup":"FA Cup",
    "Copa del Rey":"Copa del Rey","DFB Pokal":"DFB Pokal","Coppa Italia":"Coppa Italia"
  }
};

function num(v,d=0){ const n=Number(v); return Number.isFinite(n)?n:d; }
function clamp(x,a,b){return Math.max(a,Math.min(b,x));}
function logistic(x){return 1/(1+Math.exp(-x));}
function softmax(xs){
  const m=Math.max(...xs), es=xs.map(x=>Math.exp(x-m)), s=es.reduce((a,b)=>a+b,0);
  return es.map(x=>x/s);
}
function teamDivision(t){
  return t?.division || t?.currentLeague || t?.league || t?.domesticLeague || "";
}
function formPoints(t){
  const f=t?.form || t?.last5 || t?.recentForm || "";
  if(Array.isArray(f)) return f.slice(-5).reduce((s,x)=>s+(String(x).toUpperCase().startsWith("W")?3:String(x).toUpperCase().startsWith("D")?1:0),0);
  return String(f).toUpperCase().split("").slice(-5).reduce((s,x)=>s+(x==="W"?3:x==="D"?1:0),0);
}
function recentGF(t){return num(t?.recentGF ?? t?.goalsFor5 ?? t?.last5GF,0);}
function recentGA(t){return num(t?.recentGA ?? t?.goalsAgainst5 ?? t?.last5GA,0);}
function rating(t){
  return num(t?.avgRating ?? t?.seasonRating ?? t?.fotmobRating ?? t?.rating,6.5);
}
function squadValue(t){return num(t?.squadValue ?? t?.transferValue ?? t?.marketValue,0);}
function lineupRating(t){
  return num(t?.lineupRating ?? t?.startingXIRating ?? t?.xiRating, rating(t));
}
function availability(t){return num(t?.availability ?? t?.availablePct,100);}
function h2h(t){return num(t?.h2hScore ?? t?.h2h,0);}
function xg(t){return num(t?.xgFor ?? t?.xg,0);}

function analyzeMatch(m){
  const H=m.homeData||m.homeTeamData||m.home||{};
  const A=m.awayData||m.awayTeamData||m.away||{};
  const hs=MODEL.leagueStrength[teamDivision(H)] ?? MODEL.leagueStrength[m.homeDivision] ?? 1500;
  const as=MODEL.leagueStrength[teamDivision(A)] ?? MODEL.leagueStrength[m.awayDivision] ?? 1500;

  // Division/quality gap is the largest structural input.
  let h=hs, a=as;
  const sameDiv=teamDivision(H) && teamDivision(H)===teamDivision(A);
  const divGap=(hs-as)/20;
  h += divGap; a -= divGap;

  // Current table position only matters when known; cross-division position is NOT
  // directly compared (a #4 in League One is not a #4 in Championship).
  const hp=num(H.position ?? m.homePosition,0), ap=num(A.position ?? m.awayPosition,0);
  if(hp>0 && ap>0){
    if(sameDiv){
      const tableEdge=clamp((ap-hp)*7,-45,45);
      h += tableEdge; a -= tableEdge;
    } else {
      h += clamp((21-hp)*1.6,-15,15);
      a += clamp((21-ap)*1.6,-15,15);
    }
  }

  // Form: team-specific, bounded.
  const hf=formPoints(H), af=formPoints(A);
  h += clamp((hf-af)*7,-35,35); a -= clamp((hf-af)*7,-35,35);
  h += clamp((recentGF(H)-recentGA(H))*4,-20,20);
  a += clamp((recentGF(A)-recentGA(A))*4,-20,20);

  // Player/lineup quality: only apply if real data exists.
  const lrH=lineupRating(H), lrA=lineupRating(A);
  const qH=(lrH-6.5)*32 + Math.log1p(squadValue(H))*2.0;
  const qA=(lrA-6.5)*32 + Math.log1p(squadValue(A))*2.0;
  h += clamp(qH,-25,45); a += clamp(qA,-25,45);

  // Availability: missing players should hurt the affected team.
  h += clamp((availability(H)-availability(A))*0.55,-20,20);
  a += clamp((availability(A)-availability(H))*0.55,-20,20);

  // xG, if supplied.
  h += clamp((xg(H)-xg(A))*8,-25,25);
  a += clamp((xg(A)-xg(H))*8,-25,25);

  // H2H is deliberately small.
  const hh=h2h(H), ha=h2h(A);
  h += clamp((hh-ha)*0.18,-10,10);
  a += clamp((ha-hh)*0.18,-10,10);

  // Home advantage: small, never a deciding force by itself.
  const homeAdv=sameDiv?24:10;
  h += homeAdv;

  const diff=h-a;

  // Draw is explicitly modeled. Close ratings -> materially higher draw probability.
  const baseDraw=sameDiv?0.285:0.255;
  const draw=Math.exp(-Math.abs(diff)/105)*baseDraw;
  const winMass=1-draw;
  const ph=logistic(diff/115)*winMass;
  const pa=winMass-ph;

  // Make probabilities sum exactly to 1.
  let probs=[clamp(ph,0.03,0.92),clamp(draw,0.06,0.40),clamp(pa,0.03,0.92)];
  const sum=probs.reduce((a,b)=>a+b,0); probs=probs.map(x=>x/sum);

  const labels=[m.home,m.away,"Draw"];
  const idx=probs.indexOf(Math.max(...probs));
  const verdict=idx===0?`WIN: ${m.home}`:idx===2?"DRAW":`WIN: ${m.away}`;
  const margin=Math.max(...probs)-[...probs].sort((a,b)=>b-a)[1];

  const evidence=[
    `${teamDivision(H)||m.homeDivision||"Division unknown"} vs ${teamDivision(A)||m.awayDivision||"Division unknown"} — division strength is ${Math.abs(hs-as).toFixed(0)} rating points apart.`,
    sameDiv ? `Both teams are in the same division, so league position is directly comparable.` :
      `Different divisions: league positions are NOT directly compared; division strength carries the main structural weight.`,
    `Recent form: ${m.home} ${hf}/15 vs ${m.away} ${af}/15.`,
    `Home advantage is capped at ${homeAdv} rating points and cannot dominate team quality.`,
    `Lineup/players: ${lrH.toFixed(2)} vs ${lrA.toFixed(2)} average available XI/season rating where supplied.`,
    `Availability: ${availability(H).toFixed(0)}% vs ${availability(A).toFixed(0)}% where supplied.`,
  ];
  if(xg(H)||xg(A)) evidence.push(`xG input: ${xg(H).toFixed(2)} vs ${xg(A).toFixed(2)}.`);
  if(h2h(H)||h2h(A)) evidence.push(`H2H signal is included with low weight to avoid overfitting old meetings.`);

  const dataFields=[hp,ap,hf,af,lrH,lrA,availability(H),availability(A),xg(H),xg(A),squadValue(H),squadValue(A)];
  const known=dataFields.filter(v=>v!==0 && v!==100).length;
  const completeness=clamp(35+known/dataFields.length*65,35,100);
  const confidence=clamp(50+margin*120+(completeness-50)*0.25,45,94);

  return {probs,verdict,confidence,completeness,homeScore:h,awayScore:a,diff,evidence,
    projected: probs[0]>probs[2]&&probs[0]>probs[1]?"1-0":probs[2]>probs[0]&&probs[2]>probs[1]?"0-1":"1-1"};
}

function renderDeepAnalysis(m){
  const r=analyzeMatch(m);
  const pct=r.probs.map(x=>Math.round(x*100));
  return `
  <div class="deep-analysis">
    <div class="verdict ${r.verdict.startsWith("DRAW")?"draw":""}">
      <div class="eyebrow">CALCULATED BEST PLAY</div>
      <div class="verdict-main">${r.verdict}</div>
      <div class="verdict-sub">Confidence ${Math.round(r.confidence)}/100 · Projected ${r.projected}</div>
    </div>
    <div class="prob-grid">
      <div><b>${m.home}</b><strong>${pct[0]}%</strong></div>
      <div><b>DRAW</b><strong>${pct[1]}%</strong></div>
      <div><b>${m.away}</b><strong>${pct[2]}%</strong></div>
    </div>
    <div class="evidence-box">
      <h4>DEEP EVIDENCE</h4>
      ${r.evidence.map(x=>`<p>• ${x}</p>`).join("")}
      <p class="data-quality">Data completeness: ${Math.round(r.completeness)}% — unavailable fields are not invented.</p>
    </div>
    <div class="lineup-list">
      <h4>ROTIWIRE LINEUP CHECK</h4>
      <p>${m.rotowireUrl?`<a target="_blank" rel="noopener" href="${m.rotowireUrl}">Open RotoWire lineup listing →</a>`:"RotoWire listing not available for this fixture."}</p>
      <div class="xi-columns">
        <div><b>${m.home}</b><br>${(m.homeLineup||[]).map(p=>`${p.position||""} ${p.name||p}`).join("<br>")||"No lineup data yet"}</div>
        <div><b>${m.away}</b><br>${(m.awayLineup||[]).map(p=>`${p.position||""} ${p.name||p}`).join("<br>")||"No lineup data yet"}</div>
      </div>
    </div>
  </div>`;
}

window.openDeepAnalysis=function(match){
  const el=document.getElementById(`analysis-${match.id}`)||document.getElementById("analysis-panel");
  if(el){el.innerHTML=renderDeepAnalysis(match);el.classList.add("open");el.scrollIntoView({behavior:"smooth",block:"nearest"});}
};
