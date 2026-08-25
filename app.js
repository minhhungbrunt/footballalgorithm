const App=(()=>{
  const state={matches:[],league:"ALL",sort:"time",query:"",open:null};
  const $=id=>document.getElementById(id);
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const pct=n=>n==null?"—":Math.round(Number(n)*100)+"%";
  const leagues=["ALL","Premier League","Championship","League One","LaLiga","LaLiga 2","Copa del Rey","Bundesliga","2. Bundesliga","DFB Pokal","Serie A","Serie B","Coppa Italia","Ligue 1","Ligue 2","Coupe de France","Eredivisie","Eerste Divisie","Primeira Liga","Liga Portugal 2","FA Cup","EFL Cup","UEFA Champions League","UEFA Europa League","UEFA Conference League","Scottish Premiership","Belgian Pro League","Turkish Super Lig","Saudi Pro League","MLS","Brasileirao","Liga MX"];

  async function init(){
    bind();buildTabs();
    try{
      const r=await fetch("data/fixtures.json?"+Date.now(),{cache:"no-store"});
      if(!r.ok)throw Error(r.status);const d=await r.json();
      state.matches=d.matches||[];$('updatedAt').textContent=d.updated||"—";$('fixtureCount').textContent=state.matches.length+" fixtures";
      $('dataStatus').innerHTML="<i></i> Live data";$('dataStatus').className="status-dot live";
    }catch(e){state.matches=[];$('updatedAt').textContent="Data unavailable";$('fixtureCount').textContent="0 fixtures";$('dataStatus').innerHTML="<i></i> Offline";}
    render();
  }
  function bind(){
    $('refreshBtn').onclick=()=>location.reload();
    $('searchInput').oninput=e=>{state.query=e.target.value.toLowerCase();render()};
    document.querySelectorAll('.sort-btn').forEach(b=>b.onclick=()=>{document.querySelectorAll('.sort-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.sort=b.dataset.sort;render()});
  }
  function buildTabs(){
    $('leagueTabs').innerHTML=leagues.map(l=>`<button class="tab ${l==='ALL'?'active':''}" data-league="${esc(l)}">${esc(l)}</button>`).join('');
    document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.league=b.dataset.league;render()});
  }
  function filtered(){
    let a=state.matches.filter(m=>state.league==='ALL'||m.competition===state.league);
    if(state.query)a=a.filter(m=>(m.home+' '+m.away+' '+m.competition).toLowerCase().includes(state.query));
    if(state.sort==='model')a.sort((x,y)=>(y.model?.confidence||0)-(x.model?.confidence||0));else a.sort((x,y)=>timeValue(x)-timeValue(y));
    return a;
  }
  function timeValue(m){const d=Date.parse(m.time||'');return isNaN(d)?999999999999:d}
  function render(){
    const a=filtered();renderFeatured(a);$('matchday').innerHTML='';
    if(!a.length){$('matchday').innerHTML='<div class="empty"><b>No current fixtures loaded.</b><br><br>GitHub Action should refresh FotMob automatically.</div>';return}
    const groups={};a.forEach(m=>(groups[m.competition]??=[]).push(m));
    Object.entries(groups).forEach(([league,g])=>{
      const block=document.createElement('section');block.className='league-block';
      block.innerHTML=`<div class="league-head"><div class="league-title"><div class="league-badge">${leagueIcon(league)}</div><h2>${esc(league)}</h2><span>${g.length} MATCH${g.length===1?'':'ES'}</span></div></div><div class="league-games"></div>`;
      const list=block.querySelector('.league-games');g.forEach(m=>list.appendChild(row(m)));$('matchday').appendChild(block);
    });
  }
  function leagueIcon(l){return ({'Premier League':'PL','LaLiga':'LL','Bundesliga':'BL','Serie A':'SA','Ligue 1':'L1','Eredivisie':'ER','Primeira Liga':'PT','UEFA Champions League':'UCL','EFL Cup':'EFL'}[l]||'FC')}
  function displayTime(m){if(m.status==='live')return 'LIVE';if(m.status==='finished')return 'FT';if(!m.time)return 'TBD';const d=Date.parse(m.time);return isNaN(d)?m.time:new Intl.DateTimeFormat(undefined,{hour:'numeric',minute:'2-digit'}).format(d)}

  function row(m){
    const el=document.createElement('article');el.className='match-row'+(m.status==='live'?' live':'')+(state.open===String(m.id)?' expanded':'');el.id='match-'+m.id;
    const model=m.model||fallbackModel(m);const verdict=model.best||'—';
    el.innerHTML=`<div class="match-time ${m.status==='live'?'live':''}">${esc(displayTime(m))}</div>
      <div class="teams"><span class="team-home">${esc(m.home)}</span><span class="dash">vs</span><span class="team-away">${esc(m.away)}</span></div>
      <div class="positions">${m.homePos?`<b>#${esc(m.homePos)}</b>`:'—'} <span>·</span> ${m.awayPos?`<b>#${esc(m.awayPos)}</b>`:'—'}</div>
      <div class="mini-verdict"><strong>${esc(verdict)}</strong><span>${esc(model.confidence||'—')}/100 confidence</span></div>
      <button class="analyze-btn">${state.open===String(m.id)?'CLOSE':'ANALYZE'}</button>
      <div class="analysis-panel">${analysis(m)}</div>`;
    el.querySelector('.analyze-btn').onclick=()=>{const id=String(m.id);state.open=state.open===id?null:id;render();if(state.open===id)setTimeout(()=>document.getElementById('match-'+id)?.scrollIntoView({behavior:'smooth',block:'nearest'}),30)};
    return el;
  }

  function fallbackModel(m){
    const h=Number(m.homeStrength||1500)+(18-Number(m.homePos||18))*5;const a=Number(m.awayStrength||1500)+(18-Number(m.awayPos||18))*5;const diff=h+22-a;
    const home=1/(1+Math.pow(10,-diff/400)),away=1-home;const draw=Math.min(.31,Math.max(.20,.28-Math.abs(diff)/2500));const scale=1-draw;return {home:home*scale,draw,away:away*scale,best:home>away?'WIN: '+m.home:'WIN: '+m.away,confidence:Math.round(50+Math.abs(home-away)*70),score:'—',factors:{'Division quality':50,'League position':50,'Recent form':50,'Starting XI quality':50,'Squad value':50,'Availability':50,'Home advantage':50,'H2H':50}};
  }
  function lineupData(m,side){
    const d=m.detail||{};const q=(d.lineups||[]).find(x=>x.side===side);const rw=(m.rotowire||{})[side]||{};
    return {fotmob:q||null,rotowire:rw};
  }
  function money(v){if(v==null)return '—';v=Number(v);if(!isFinite(v))return '—';if(v>=100000000)return '€'+(v/1e6).toFixed(0)+'M';if(v>=1000000)return '€'+(v/1e6).toFixed(1)+'M';if(v>=1000)return '€'+Math.round(v/1000)+'K';return '€'+Math.round(v)}
  function playerRows(m,side){
    const q=lineupData(m,side);const starters=q.fotmob?.starters||[];const predicted=q.rotowire?.players||[];const use=starters.length?starters:predicted;
    if(!use.length)return `<div class="lineup-empty">No lineup data yet.</div>`;
    const confirmed=!!starters.length;return `<div class="lineup-status"><b>${confirmed?'FotMob lineup':'RotoWire predicted XI'}</b><span>${confirmed?'CONFIRMED / AVAILABLE':'PREDICTED'}</span></div><div class="player-list">${use.slice(0,11).map((p,i)=>`<div class="player-row"><span class="player-pos">${esc(p.position||'—')}</span><span class="player-name">${esc(p.name||'—')}</span><span class="player-rating">${p.rating!=null?esc(p.rating):'—'}</span><span class="player-value">${money(p.transferValue)}</span></div>`).join('')}</div>`;
  }
  function injuries(m,side){
    const team=side==='home'?m.home:m.away;const fot=(m.detail?.injuries||[]).filter(x=>x.team===team);const rw=(m.rotowire?.[side]?.injuries)||[];const arr=fot.length?fot:rw;
    if(!arr.length)return '<span class="ok">No reported absences</span>';
    return arr.map(x=>`<span class="injury"><b>${esc(x.name||'Unknown')}</b> ${esc(x.reason||x.status||'OUT')}</span>`).join('');
  }
  function analysis(m){
    const x=m.model||fallbackModel(m),f=x.factors||{},d=m.detail||{};const hL=m.homeLeague||x.homeLeague||'Unavailable',aL=m.awayLeague||x.awayLeague||'Unavailable';
    const rwLink=m.rotowire?.url||null;
    return `<div class="analysis-grid">
      <div class="analysis-card"><h3>MODEL DECISION</h3><div class="decision"><div class="decision-title">CALCULATED VERDICT</div><div class="decision-value">${esc(x.best)}</div><div class="confidence">Confidence ${esc(x.confidence)}/100</div><div class="score">Projected ${esc(x.score||'—')}</div></div><div class="news-line"><b>${esc(m.competition)}</b> · Current division: <b>${esc(hL)}</b> vs <b>${esc(aL)}</b> · Position: ${m.homePos||'—'} vs ${m.awayPos||'—'}</div><div class="news-line">${x.crossDivision?'Cross-division adjustment is active: division quality is weighted heavily and venue is deliberately reduced.':'Same-division model: position, form and lineup quality carry more weight than venue.'}</div></div>
      <div class="analysis-card"><h3>PROBABILITIES</h3><div class="probs"><div class="prob"><small>${esc(m.home)}</small><b>${pct(x.home)}</b></div><div class="prob"><small>Draw</small><b>${pct(x.draw)}</b></div><div class="prob"><small>${esc(m.away)}</small><b>${pct(x.away)}</b></div></div><div class="evidence-grid"><div><b>xG projection</b><span>${x.expectedGoals?x.expectedGoals[0]+' – '+x.expectedGoals[1]:'—'}</span></div><div><b>BTTS</b><span>Model probability based on projected goals</span></div><div><b>Data completeness</b><span>${esc(x.dataCompleteness??'—')}/8 evidence blocks</span></div></div></div>
      <div class="analysis-card"><h3>MODEL FACTORS</h3><div class="factor-grid">${Object.entries(f).map(([k,v])=>`<div class="factor"><label>${esc(k)}</label><strong>${esc(v)}/100</strong></div>`).join('')}</div></div>
      <div class="analysis-card lineup-card"><div class="lineup-head"><h3>${esc(m.home)} · XI</h3>${rwLink?`<a href="${esc(rwLink)}" target="_blank" rel="noopener">RotoWire</a>`:''}</div>${playerRows(m,'home')}<div class="absence-box"><b>Availability</b>${injuries(m,'home')}</div></div>
      <div class="analysis-card lineup-card"><div class="lineup-head"><h3>${esc(m.away)} · XI</h3>${rwLink?`<a href="${esc(rwLink)}" target="_blank" rel="noopener">RotoWire</a>`:''}</div>${playerRows(m,'away')}<div class="absence-box"><b>Availability</b>${injuries(m,'away')}</div></div>
      <div class="analysis-card"><h3>DEEP EVIDENCE</h3><div class="deep-grid"><div><b>Form</b><span>${esc(m.homeForm?.last5||'—')} · ${m.homeForm?.points??'—'} pts vs ${esc(m.awayForm?.last5||'—')} · ${m.awayForm?.points??'—'} pts</span></div><div><b>Goals in last 5</b><span>${m.homeForm?.gf??'—'}–${m.homeForm?.ga??'—'} vs ${m.awayForm?.gf??'—'}–${m.awayForm?.ga??'—'}</span></div><div><b>FotMob XI</b><span>${d.homeLineupRating??'—'} vs ${d.awayLineupRating??'—'} avg rating · ${d.homeFormation||'—'} vs ${d.awayFormation||'—'}</span></div><div><b>H2H</b><span>${d.h2hHomeWins!=null?`${d.h2hHomeWins} wins · ${d.h2hDraws||0} draws · ${d.h2hAwayWins||0} wins`:'Not available'}</span></div><div><b>Match xG</b><span>${d.xgHome!=null?`${d.xgHome} – ${d.xgAway}`:'Pre-match unavailable'}</span></div><div><b>Lineup status</b><span>${d.lineupConfirmed?'FotMob confirmed':'Predicted / partial'}${m.rotowire?' + RotoWire cross-check':''}</span></div></div><div class="news-line"><b>Player-quality method:</b> the model blends current FotMob XI ratings with season player rating and transfer-value data when available. Transfer value is deliberately a secondary signal; it cannot override sustained performance, division strength or lineup availability.</div></div>
    </div>`;
  }
  function renderFeatured(a){
    const m=a[0];if(!m){$('featuredContent').innerHTML='<div class="empty">No featured match.</div>';return}const x=m.model||fallbackModel(m);
    $('featuredContent').innerHTML=`<div class="featured-match"><div class="featured-team"><div class="name">${esc(m.home)}</div><div class="pos">${esc(m.homeLeague||'Division unavailable')}${m.homePos?' · #'+esc(m.homePos):''}</div></div><div class="featured-vs"><div class="time">${esc(displayTime(m))}</div><div class="vs">VS · ${esc(m.competition)}</div></div><div class="featured-team"><div class="name">${esc(m.away)}</div><div class="pos">${esc(m.awayLeague||'Division unavailable')}${m.awayPos?' · #'+esc(m.awayPos):''}</div></div></div><div class="verdict"><span class="verdict-label">CALCULATED VERDICT</span><span class="verdict-main">${esc(x.best)}</span><span class="verdict-meta">${esc(x.confidence)}/100 · projected ${esc(x.score||'—')}</span></div>`;
  }
  return {init};
})();
App.init();
