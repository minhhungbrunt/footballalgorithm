const App=(()=>{
  const state={matches:[],league:"ALL",sort:"time",query:"",open:null,source:""};
  const $=id=>document.getElementById(id);
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const pct=n=>n==null?"—":Math.round(n*100)+"%";
  const leagues=["ALL","Premier League","Championship","League One","LaLiga","LaLiga 2","Copa del Rey","Bundesliga","2. Bundesliga","DFB Pokal","Serie A","Serie B","Coppa Italia","Ligue 1","Ligue 2","Coupe de France","Eredivisie","Eerste Divisie","Primeira Liga","Liga Portugal 2","FA Cup","EFL Cup","UEFA Champions League","UEFA Europa League","UEFA Conference League","Scottish Premiership","Belgian Pro League","Turkish Super Lig","Saudi Pro League","MLS","Brasileirao","Liga MX"];

  async function init(){
    bind();
    buildTabs();
    try{
      const r=await fetch("data/fixtures.json?"+Date.now(),{cache:"no-store"});
      if(!r.ok)throw new Error(r.status);
      const d=await r.json();
      state.matches=d.matches||[];
      state.source=d.source||"FotMob";
      $("updatedAt").textContent=d.updated||"Unknown";
      $("fixtureCount").textContent=state.matches.length+" fixtures";
      $("dataStatus").innerHTML="<i></i> Live data";
      $("dataStatus").className="status-dot live";
    }catch(e){
      state.matches=demo();
      state.source="Local fallback";
      $("updatedAt").textContent="Fallback data";
      $("fixtureCount").textContent=state.matches.length+" fixtures";
    }
    render();
  }

  function demo(){
    return [
      mk("Manchester City","Arsenal","Premier League","12:30",2,3,1),
      mk("Liverpool","Chelsea","Premier League","15:00",1,5,2),
      mk("Real Madrid","Barcelona","LaLiga","20:00",1,2,3),
      mk("Bayern Munich","Dortmund","Bundesliga","18:30",1,4,4),
      mk("Inter","AC Milan","Serie A","20:45",2,6,5),
      mk("PSG","Marseille","Ligue 1","20:45",1,4,6),
      mk("Ajax","PSV","Eredivisie","18:45",2,1,7),
      mk("Benfica","Sporting CP","Primeira Liga","20:15",1,2,8)
    ];
  }
  function mk(h,a,l,t,hp,ap,id){return {id:String(id),home:h,away:a,competition:l,time:t,homePos:hp,awayPos:ap,status:"upcoming",model:quickModel(h,a,hp,ap,{competition:l,homeLeague:l,awayLeague:l})}}

  // Model v2: division-aware Elo-style baseline.
  // Cross-division cup games use the teams' domestic league strength first;
  // home advantage is deliberately small and form/H2H are secondary.
  function quickModel(h,a,hp,ap,meta={}){
    const leagueRating={
      "Premier League":1860,"LaLiga":1840,"Bundesliga":1830,"Serie A":1810,
      "Ligue 1":1780,"Eredivisie":1700,"Primeira Liga":1690,
      "Championship":1640,"Scottish Premiership":1600,"Belgian Pro League":1575,
      "Turkish Super Lig":1575,"MLS":1535,"Saudi Pro League":1530,
      "LaLiga 2":1475,"2. Bundesliga":1475,"Serie B":1470,"Ligue 2":1450,
      "Liga Portugal 2":1435,"League One":1395,"Eerste Divisie":1390,
      "Brasileirao":1650,"Liga MX":1625,"League Two":1240
    };
    const hLeague=meta.homeLeague||meta.competition;
    const aLeague=meta.awayLeague||meta.competition;
    let hs=meta.homeStrength||leagueRating[hLeague]||1500;
    let as=meta.awayStrength||leagueRating[aLeague]||1500;

    // Same-division table position: useful, but never allowed to dominate.
    // Lower rank number = stronger.
    if(hp && ap && hLeague===aLeague){
      hs += Math.max(-70,Math.min(70,(25-hp)*4));
      as += Math.max(-70,Math.min(70,(25-ap)*4));
    }

    // Recent form only gets a modest adjustment. If the updater eventually
    // supplies form scores, they can move the baseline by at most ~45 Elo.
    if(meta.homeFormRating!=null) hs += Math.max(-45,Math.min(45,meta.homeFormRating));
    if(meta.awayFormRating!=null) as += Math.max(-45,Math.min(45,meta.awayFormRating));

    const cross=Boolean(meta.crossDivision || (hLeague&&aLeague&&hLeague!==aLeague));

    // Home field is a small nudge, not a 40% starting probability.
    // In a cross-division cup tie it is reduced further because venue cannot
    // erase a substantial tier gap.
    const homeAdv=cross?28:55;
    const diff=(hs+homeAdv)-as;

    // Convert strength difference into expected goals and a Poisson 1X2.
    // This gives a real draw probability instead of forcing it from a
    // leftover percentage.
    const lambdaH=Math.max(0.25,1.35*Math.exp(diff/850));
    const lambdaA=Math.max(0.25,1.05*Math.exp(-diff/850));
    const pois=(k,l)=>Math.exp(-l)*Math.pow(l,k)/factorial(k);
    const maxGoals=7;
    let home=0,draw=0,away=0,btts=0;
    for(let i=0;i<=maxGoals;i++){
      for(let j=0;j<=maxGoals;j++){
        const p=pois(i,lambdaH)*pois(j,lambdaA);
        if(i>j)home+=p; else if(i===j)draw+=p; else away+=p;
        if(i>0&&j>0)btts+=p;
      }
    }
    const norm=home+draw+away;
    home/=norm;draw/=norm;away/=norm;

    // Small evidence modifiers. They cannot overturn a large division gap.
    const h2h=Number(meta.h2hEdge||0);
    const availability=Number(meta.availabilityEdge||0);
    const modifier=Math.max(-0.045,Math.min(0.045,(h2h+availability)/100));
    home=Math.max(.01,home+modifier);
    away=Math.max(.01,away-modifier);
    const n=home+draw+away;home/=n;draw/=n;away/=n;

    const vals=[["WIN: "+h,home],["DRAW",draw],["WIN: "+a,away]].sort((x,y)=>y[1]-x[1]);
    const top=vals[0];
    const confidence=Math.round(Math.max(54,Math.min(94,50+Math.abs(top[1]-.333)*105)));
    const score=projectedScore(lambdaH,lambdaA);

    return {
      home,draw,away,btts,
      best:top[0],
      confidence,
      score,
      factors:{
        "Division strength":Math.round(50+Math.max(-50,Math.min(50,(hs-as)/4))),
        "Table position":hLeague===aLeague&&hp&&ap?Math.round(50+Math.max(-40,Math.min(40,(ap-hp)*2.2))):50,
        "Home advantage":cross?54:62,
        "Form":meta.homeFormRating!=null||meta.awayFormRating!=null?Math.round(50+(Number(meta.homeFormRating||0)-Number(meta.awayFormRating||0))/2):50,
        "H2H":50+Math.round(Math.max(-10,Math.min(10,h2h))),
        "Availability":50+Math.round(Math.max(-10,Math.min(10,availability)))
      },
      note:cross
        ? `Cross-division model: ${hLeague||"unknown division"} vs ${aLeague||"unknown division"}. Division strength is weighted ahead of venue.`
        : `Same-division model: table position and form are secondary to underlying team strength.`,
      divisionGap:Math.round(as-hs),
      homeLeague:hLeague,
      awayLeague:aLeague
    };
  }

  function factorial(n){let x=1;for(let i=2;i<=n;i++)x*=i;return x;}
  function projectedScore(h,a){
    let bh=0,ba=0,ph=0,pa=0;
    for(let k=0;k<=7;k++){
      const pH=Math.exp(-h)*Math.pow(h,k)/factorial(k);
      const pA=Math.exp(-a)*Math.pow(a,k)/factorial(k);
      ph+=k*pH;pa+=k*pA;
    }
    bh=Math.max(0,Math.min(5,Math.round(ph)));
    ba=Math.max(0,Math.min(5,Math.round(pa)));
    return `${bh}–${ba}`;
  }


  function bind(){
    $("refreshBtn").onclick=()=>location.reload();
    $("searchInput").oninput=e=>{state.query=e.target.value.toLowerCase();render()};
    document.querySelectorAll(".sort-btn").forEach(b=>b.onclick=()=>{
      document.querySelectorAll(".sort-btn").forEach(x=>x.classList.remove("active"));
      b.classList.add("active");state.sort=b.dataset.sort;render();
    });
  }
  function buildTabs(){
    $("leagueTabs").innerHTML=leagues.map(l=>`<button class="tab ${l==="ALL"?"active":""}" data-league="${esc(l)}">${esc(l)}</button>`).join("");
    document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>{
      document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));
      b.classList.add("active");state.league=b.dataset.league;render();
    });
  }

  function filtered(){
    let a=state.matches.filter(m=>state.league==="ALL"||m.competition===state.league);
    if(state.query)a=a.filter(m=>(m.home+" "+m.away+" "+m.competition).toLowerCase().includes(state.query));
    if(state.sort==="model")a.sort((x,y)=>(y.model?.confidence||0)-(x.model?.confidence||0));
    else a.sort((x,y)=>timeValue(x)-timeValue(y));
    return a;
  }
  function timeValue(m){const d=Date.parse(m.time||"");return isNaN(d)?999999999999:d}
  function render(){
    const a=filtered();
    renderFeatured(a);
    $("matchday").innerHTML="";
    if(!a.length){
      $("featuredContent").innerHTML='<div class="empty">Waiting for the automatic FotMob matchday update.</div>';
      $("matchday").innerHTML='<div class="empty"><b>No current fixtures loaded yet.</b><br><br>Run <b>Actions → Football Edge — Update Matchday → Run workflow</b> once. After that GitHub will refresh the fixture file automatically every 15 minutes.</div>';
      return;
    }
    const groups={};
    a.forEach(m=>(groups[m.competition]??=[]).push(m));
    Object.entries(groups).forEach(([league,g])=>{
      const block=document.createElement("section");block.className="league-block";
      block.innerHTML=`<div class="league-head"><div class="league-title"><div class="league-badge">${leagueIcon(league)}</div><h2>${esc(league)}</h2><span>${g.length} MATCH${g.length===1?"":"ES"}</span></div></div><div class="league-games"></div>`;
      const list=block.querySelector(".league-games");
      g.forEach(m=>list.appendChild(row(m)));
      $("matchday").appendChild(block);
    });
  }
  function leagueIcon(l){return ({'Premier League':'PL','LaLiga':'LL','Bundesliga':'BL','Serie A':'SA','Ligue 1':'L1','Eredivisie':'ER','Primeira Liga':'PT'}[l]||'FC')}

  function row(m){
    const el=document.createElement("article");el.className="match-row"+(m.status==="live"?" live":"");el.id="match-"+m.id;
    const model=m.model||quickModel(m.home,m.away,m.homePos,m.awayPos,m);
    el.innerHTML=`
      <div class="match-time ${m.status==="live"?"live":""}">${esc(displayTime(m))}</div>
      <div class="teams"><span class="team-home">${esc(m.home)}</span><span class="dash">vs</span><span class="team-away">${esc(m.away)}</span></div>
      <div class="positions">${m.homePos?`<b>#${esc(m.homePos)}</b>`:"—"} <span>·</span> ${m.awayPos?`<b>#${esc(m.awayPos)}</b>`:"—"}</div>
      <div class="mini-verdict"><strong>${esc(model.best)}</strong><span>${esc(model.confidence)}/100 confidence</span></div>
      <button class="analyze-btn" data-id="${esc(m.id)}">${state.open===String(m.id)?"CLOSE":"ANALYZE"}</button>
      <div class="analysis-panel">${analysis(m)}</div>`;
    el.querySelector(".analyze-btn").onclick=()=>{
      const id=String(m.id);
      state.open=state.open===id?null:id;
      render();
      if(state.open===id)setTimeout(()=>document.getElementById("match-"+id)?.scrollIntoView({behavior:"smooth",block:"nearest"}),20);
    };
    if(state.open===String(m.id))el.classList.add("expanded");
    return el;
  }

  function displayTime(m){
    if(m.status==="live")return "LIVE";
    if(m.status==="finished")return "FT";
    if(!m.time)return "TBD";
    const d=Date.parse(m.time);
    if(isNaN(d))return m.time;
    return new Intl.DateTimeFormat(undefined,{hour:"numeric",minute:"2-digit"}).format(d);
  }

  function analysis(m){
    const x=m.model||quickModel(m.home,m.away,m.homePos,m.awayPos,m);
    const factors=x.factors||{};
    return `<div class="analysis-grid">
      <div class="analysis-card">
        <h3>Result probabilities</h3>
        <div class="probs">
          <div class="prob"><small>${esc(m.home)}</small><b>${pct(x.home)}</b></div>
          <div class="prob"><small>Draw</small><b>${pct(x.draw)}</b></div>
          <div class="prob"><small>${esc(m.away)}</small><b>${pct(x.away)}</b></div>
        </div>
        <div class="bar-row"><div class="bar-top"><span>BTTS</span><span>${pct(x.btts)}</span></div><div class="bar"><i style="width:${Math.round((x.btts||0)*100)}%"></i></div></div>
        <div class="news-line"><b>Projected score:</b> ${esc(x.score||"—")}</div>
      </div>
      <div class="analysis-card">
        <h3>Decision</h3>
        <div class="decision"><div class="decision-title">MODEL VERDICT</div><div class="decision-value">${esc(x.best)}</div><div class="confidence">Confidence ${esc(x.confidence)}/100</div><div class="score">Projected ${esc(x.score||"—")}</div></div>
        <div class="news-line"><b>Competition:</b> ${esc(m.competition)} · <b>Division:</b> ${esc(x.homeLeague||"—")} vs ${esc(x.awayLeague||"—")} · <b>Position:</b> ${m.homePos?esc(m.homePos):"—"} vs ${m.awayPos?esc(m.awayPos):"—"}</div>
      </div>
      <div class="analysis-card">
        <h3>Model factors</h3>
        <div class="factor-grid">${Object.entries(factors).map(([k,v])=>`<div class="factor"><label>${esc(k)}</label><strong>${esc(v)}/100</strong></div>`).join("")}</div>
        <div class="news-line"><b>Team news:</b> ${esc(x.note||"Live data pending.")}</div>
      </div>
    </div>`;
  }

  function renderFeatured(a){
    const m=a[0];
    if(!m){$("featuredContent").innerHTML='<div class="empty">No featured match.</div>';return}
    const x=m.model||quickModel(m.home,m.away,m.homePos,m.awayPos,m);
    $("featuredContent").innerHTML=`<div class="featured-match">
      <div class="featured-team"><div class="name">${esc(m.home)}</div><div class="pos">${m.homeLeague?(m.homePos?"#"+esc(m.homePos)+" · ":"")+esc(m.homeLeague):m.competition}</div></div>
      <div class="featured-vs"><div class="time">${esc(displayTime(m))}</div><div class="vs">VS · ${esc(m.competition)}</div></div>
      <div class="featured-team"><div class="name">${esc(m.away)}</div><div class="pos">${m.awayLeague?(m.awayPos?"#"+esc(m.awayPos)+" · ":"")+esc(m.awayLeague):m.competition}</div></div>
    </div><div class="verdict"><span class="verdict-label">CALCULATED VERDICT</span><span class="verdict-main">${esc(x.best)}</span><span class="verdict-meta">${esc(x.confidence)}/100 · projected ${esc(x.score||"—")}</span></div>`;
  }
  return {init};
})();
App.init();
