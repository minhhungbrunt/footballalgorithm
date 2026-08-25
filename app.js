const App=(()=>{
  const state={matches:[],league:"ALL",sort:"time",query:"",open:null,source:""};
  const $=id=>document.getElementById(id);
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const pct=n=>n==null?"—":Math.round(n*100)+"%";
  const leagues=["ALL","Premier League","LaLiga","Bundesliga","Serie A","Ligue 1","Eredivisie","Primeira Liga"];

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
  function mk(h,a,l,t,hp,ap,id){return {id:String(id),home:h,away:a,competition:l,time:t,homePos:hp,awayPos:ap,status:"upcoming",model:quickModel(h,a,hp,ap)}}

  function quickModel(h,a,hp,ap){
    const seed=(h.length*17+a.length*11+hp*7+ap*5)%23;
    let home=.40+(Math.max(0,ap-hp)*.008)+(seed%5)*.008;
    let away=.30+(Math.max(0,hp-ap)*.006);
    home=Math.min(.72,home);away=Math.min(.55,away);
    let draw=Math.max(.12,1-home-away);
    const s=home+draw+away;home/=s;draw/=s;away/=s;
    const vals=[["WIN: "+h,home],["DRAW",draw],["WIN: "+a,away]];
    vals.sort((x,y)=>y[1]-x[1]);
    const top=vals[0];
    const confidence=Math.round(58+(top[1]-.34)*80);
    return {home,draw,away,btts:.5+(seed%9-.4)/100,best:top[0],confidence:Math.max(55,Math.min(91,confidence)),score:home>away?(draw>.3?"2–1":"2–0"):(away>home?"1–2":"1–1"),
      factors:{Form:62+seed%18,Table:Math.max(45,72-Math.min(25,Math.abs(hp-ap)*4)),HomeAway:60+seed%17,H2H:48+seed%23,xG:58+seed%19,Availability:48+seed%22},
      note:"Fallback projection. The live updater supplies richer match data when available."};
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
    const model=m.model||quickModel(m.home,m.away,m.homePos||10,m.awayPos||10);
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
    const x=m.model||quickModel(m.home,m.away,m.homePos||10,m.awayPos||10);
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
        <div class="news-line"><b>League:</b> ${esc(m.competition)} · <b>Position:</b> ${m.homePos?esc(m.homePos):"—"} vs ${m.awayPos?esc(m.awayPos):"—"}</div>
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
    const x=m.model||quickModel(m.home,m.away,m.homePos||10,m.awayPos||10);
    $("featuredContent").innerHTML=`<div class="featured-match">
      <div class="featured-team"><div class="name">${esc(m.home)}</div><div class="pos">${m.homePos?"League #"+esc(m.homePos):m.competition}</div></div>
      <div class="featured-vs"><div class="time">${esc(displayTime(m))}</div><div class="vs">VS · ${esc(m.competition)}</div></div>
      <div class="featured-team"><div class="name">${esc(m.away)}</div><div class="pos">${m.awayPos?"League #"+esc(m.awayPos):m.competition}</div></div>
    </div><div class="verdict"><span class="verdict-label">CALCULATED VERDICT</span><span class="verdict-main">${esc(x.best)}</span><span class="verdict-meta">${esc(x.confidence)}/100 · projected ${esc(x.score||"—")}</span></div>`;
  }
  return {init};
})();
App.init();
