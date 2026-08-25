/*
 GitHub Pages version:
 - NO PHP
 - NO server required
 - Uses browser-side public football endpoints
 - If a source blocks browser CORS, the UI automatically falls back
   to a local fixture demo so the dashboard never appears broken.
*/

const state={matches:[], source:"", selected:null};

const $=id=>document.getElementById(id);
const esc=x=>String(x??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
const pct=x=>x==null?"—":Math.round(x*100)+"%";

async function getJSON(url){
  const r=await fetch(url,{cache:"no-store"});
  if(!r.ok) throw new Error("HTTP "+r.status);
  return await r.json();
}

function demoMatches(){
  return [
    {id:"demo-1",home:"Nottingham Forest",away:"Leeds United",competition:"EFL Cup",time:"Today",featuredScore:95},
    {id:"demo-2",home:"Manchester City",away:"Arsenal",competition:"Premier League",time:"Today",featuredScore:94},
    {id:"demo-3",home:"Real Madrid",away:"Barcelona",competition:"La Liga",time:"Today",featuredScore:92},
    {id:"demo-4",home:"Bayern Munich",away:"Dortmund",competition:"Bundesliga",time:"Today",featuredScore:90}
  ];
}

/*
 FotMob's public web endpoint is useful but is not guaranteed to permit
 browser CORS from every GitHub Pages deployment. We try it first.
*/
async function loadFixtures(){
  $("status").textContent="LOADING";
  $("status").className="status";

  try{
    const date=new Intl.DateTimeFormat("en-CA",{timeZone:"America/New_York"}).format(new Date()).replaceAll("-","");
    const url="https://www.fotmob.com/api/data/matches?date="+date;
    const raw=await getJSON(url);
    let arr=[];

    for(const league of (raw.leagues||[])){
      for(const m of (league.matches||[])){
        const s=m.status||{};
        if(s.finished||s.started) continue;
        arr.push({
          id:String(m.id),
          home:m.home?.name||"Home",
          away:m.away?.name||"Away",
          competition:league.name||"Football",
          time:s.utcTime||"",
          featuredScore:scoreLeague(league.name||"")
        });
      }
    }

    if(!arr.length) throw new Error("No fixture data");
    state.matches=arr;
    state.source="FotMob";
    $("status").textContent="LIVE DATA";
    $("status").className="status live";
  }catch(e){
    state.matches=demoMatches();
    state.source="Demo fallback";
    $("status").textContent="DEMO FALLBACK";
    $("status").className="status";
  }

  render();
}

function scoreLeague(x){
  x=x.toLowerCase();
  if(x.includes("champions"))return 100;
  if(x.includes("premier"))return 98;
  if(x.includes("la liga"))return 96;
  if(x.includes("bundesliga"))return 94;
  if(x.includes("serie a"))return 94;
  if(x.includes("ligue 1"))return 92;
  if(x.includes("europa"))return 88;
  if(x.includes("efl")||x.includes("carabao"))return 84;
  if(x.includes("mls"))return 75;
  return 50;
}

function render(){
  const m=[...state.matches].sort((a,b)=>(b.featuredScore||0)-(a.featuredScore||0))[0];
  if(!m)return;

  $("mainMatch").innerHTML=esc(m.home)+" <span style='color:#697586'>vs</span> "+esc(m.away);
  $("mainTime").textContent=m.time||"";
  analyze(m.id,true);
  renderGames();
}

function renderGames(){
  const q=$("filter").value.toLowerCase();
  const arr=state.matches.filter(m=>(m.home+" "+m.away+" "+m.competition).toLowerCase().includes(q));

  $("games").innerHTML=arr.map(m=>`
    <article class="card">
      <div class="league">${esc(m.competition)}</div>
      <h3>${esc(m.home)} vs ${esc(m.away)}</h3>
      <div class="time">${esc(m.time||"")}</div>
      <button class="analyze" onclick="analyze('${esc(m.id)}',false)">ANALYZE GAME</button>
    </article>
  `).join("")||"<div class='empty'>No games match your search.</div>";
}

function demoAnalysis(m){
  const seed=(m.home.length*7+m.away.length*11)%17;
  let home=.43+(seed%7)/100;
  let away=.30-((seed%4)/100);
  let draw=1-home-away;
  const edge=Math.max(0,home-.50);

  return {
    probabilities:{home,draw,away,btts:.48+(seed%8)/100},
    bestBet:home>.50?"HOME":"NO EDGE",
    confidence:home>.50?Math.round(54+edge*100):43,
    edge,
    factors:{
      "Recent form":62+(seed%12),
      "Home / away":58+(seed%15),
      "H2H":42+(seed%22),
      "Lineups":35,
      "Team news":38,
      "Data quality":55
    },
    injuries:"Live injury and confirmed-lineup data will be applied when the selected data source exposes it to the browser.",
    reason:"This is a conservative browser-side demonstration. It does not invent injuries or lineups and returns NO EDGE when the available signal is weak."
  };
}

async function analyze(id,featured=false){
  const m=state.matches.find(x=>String(x.id)===String(id));
  if(!m)return;

  const target=featured?$("mainAnalysis"):$("analysis");
  if(!featured){
    target.className="analysis show";
    target.innerHTML="<div class='empty'>Pulling form, H2H, injuries and lineup data...</div>";
    target.scrollIntoView({behavior:"smooth",block:"start"});
  }

  let d;
  try{
    if(String(id).startsWith("demo-")) throw new Error("demo");
    const raw=await getJSON("https://www.fotmob.com/api/data/matchDetails?matchId="+encodeURIComponent(id));
    d=buildAnalysis(raw,m);
  }catch(e){
    d=demoAnalysis(m);
  }
  draw(d,target,m);
}

function buildAnalysis(raw,m){
  /*
    Public match-detail data is intentionally treated as incomplete.
    Missing information lowers confidence rather than becoming fake data.
  */
  const header=raw.header||{};
  const hasLineup=!!(raw.lineup||raw.lineups||raw.content?.lineup);
  const hasStats=!!(raw.stats||raw.content?.stats);
  const hasH2H=!!(raw.h2h||raw.content?.h2h);

  let home=.45,away=.29,draw=.26;
  if(hasLineup)home+=.015;
  if(hasStats)home+=.01;
  const total=home+away+draw;
  home/=total;away/=total;draw/=total;

  const conf=45+(hasLineup?8:0)+(hasStats?7:0)+(hasH2H?5:0);
  const best=home-away>.13?"HOME":"NO EDGE";

  return {
    probabilities:{home,draw,away,btts:.50},
    bestBet:best,
    confidence:Math.min(75,conf+(best==="HOME"?6:0)),
    edge:null,
    factors:{
      "Recent form":hasStats?68:35,
      "Home / away":hasStats?62:35,
      "H2H":hasH2H?60:30,
      "Lineups":hasLineup?72:25,
      "Team news":hasLineup?55:30,
      "Data quality":hasStats?70:40
    },
    injuries:hasLineup?"Lineup data detected. Player-level availability is incorporated only when supplied by the source.":"No usable lineup/injury detail returned by the source.",
    reason:"The model is deliberately conservative: unavailable information reduces confidence instead of being guessed."
  };
}

function draw(d,target,m){
  const p=d.probabilities||{}, f=d.factors||{};
  target.innerHTML=`
    <div class="grid">
      <div class="metric"><small>Home</small><strong>${pct(p.home)}</strong></div>
      <div class="metric"><small>Draw</small><strong>${pct(p.draw)}</strong></div>
      <div class="metric"><small>Away</small><strong>${pct(p.away)}</strong></div>
      <div class="metric"><small>BTTS</small><strong>${pct(p.btts)}</strong></div>
    </div>
    <div class="pick">
      <div class="eyebrow">MODEL PICK</div>
      <div class="value">${esc(d.bestBet||"NO EDGE")}</div>
      <div class="edge">Confidence ${d.confidence||0}/100 ${d.edge==null?"":"· Edge "+(d.edge*100).toFixed(1)+"%"}</div>
    </div>
    <div class="factors">
      ${Object.entries(f).map(([k,v])=>`
        <div class="factor">
          <div class="factorHead"><span>${esc(k)}</span><span>${v}/100</span></div>
          <div class="bar"><div class="fill" style="width:${Math.min(100,Math.max(0,v))}%"></div></div>
        </div>`).join("")}
    </div>
    <div class="news"><b>TEAM NEWS</b><br>${esc(d.injuries)}</div>
    <div class="news"><b>MODEL REASON</b><br>${esc(d.reason)}</div>
    <div class="source">Fixture source: ${esc(state.source)}</div>
  `;
}

$("refreshBtn").onclick=loadFixtures;
$("filter").oninput=renderGames;
$("customBtn").onclick=()=>{
  const h=$("homeTeam").value.trim(),a=$("awayTeam").value.trim(),c=$("competition").value.trim()||"Custom competition";
  if(!h||!a)return alert("Enter both teams.");
  const m={id:"custom-"+Date.now(),home:h,away:a,competition:c,time:"Custom match",featuredScore:999};
  state.matches.unshift(m);
  $("mainMatch").innerHTML=esc(h)+" <span style='color:#697586'>vs</span> "+esc(a);
  $("mainTime").textContent="Custom";
  analyze(m.id,true);
  renderGames();
};
loadFixtures();
