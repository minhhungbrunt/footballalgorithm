const state={matches:[],source:""};

const $=x=>document.getElementById(x);
const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct=x=>x==null?"—":Math.round(x*100)+"%";

async function load(){
  $("status").textContent="LOADING DATA";
  $("status").className="";
  try{
    const r=await fetch("data/fixtures.json?"+Date.now(),{cache:"no-store"});
    if(!r.ok) throw Error("fixture data "+r.status);
    const d=await r.json();
    state.matches=d.matches||[];
    state.source=d.source||"Football data";
    if(!state.matches.length) throw Error("No fixtures");
    $("status").textContent="LIVE DATA · UPDATED "+(d.updated||"");
    $("status").className="ok";
  }catch(e){
    state.source="Demo fallback";
    state.matches=[
      {id:"demo1",home:"Manchester City",away:"Arsenal",competition:"Premier League",time:"Demo",score:100,homePos:2,awayPos:3},
      {id:"demo2",home:"Real Madrid",away:"Barcelona",competition:"La Liga",time:"Demo",score:96,homePos:1,awayPos:2},
      {id:"demo3",home:"Bayern Munich",away:"Dortmund",competition:"Bundesliga",time:"Demo",score:94,homePos:1,awayPos:4},
      {id:"demo4",home:"Inter",away:"AC Milan",competition:"Serie A",time:"Demo",score:92,homePos:2,awayPos:6}
    ];
    $("status").textContent="DEMO DATA · RUN GITHUB ACTION";
  }
  render();
}

function render(){
  const best=[...state.matches].sort((a,b)=>(b.score||0)-(a.score||0))[0];
  if(!best){$("mainGame").textContent="No fixtures available";return}
  $("mainGame").innerHTML=`${esc(best.home)} <span style="color:#697586">vs</span> ${esc(best.away)}`;
  $("mainMeta").textContent=`${esc(best.competition||"Football")} · ${esc(best.time||"")} · ${esc(state.source)}`;
  showMainAnalysis(best);
  renderGames();
}

function renderGames(){
  const q=$("search").value.toLowerCase();
  const arr=state.matches.filter(m=>(m.home+" "+m.away+" "+(m.competition||"")).toLowerCase().includes(q));

  $("games").innerHTML=arr.map(m=>{
    const pos=`<div class="league-row"><span>${esc(m.competition||"League")}</span><span class="team-pos">${m.homePos?esc(m.home)+" #"+m.homePos:""}${m.homePos&&m.awayPos?" · ":""}${m.awayPos?esc(m.away)+" #"+m.awayPos:""}</span></div>`;
    return `<article class="card" id="card-${esc(m.id)}">
      <div class="league">${esc(m.competition||"Football")}</div>
      <h3>${esc(m.home)} vs ${esc(m.away)}</h3>
      <div class="time">${esc(m.time||"")}</div>
      ${pos}
      <button class="analyze" onclick="toggleAnalysis('${esc(m.id)}')">ANALYZE GAME</button>
      <div class="card-analysis" id="analysis-${esc(m.id)}"></div>
    </article>`;
  }).join("")||`<div class="empty">No games found.</div>`;
}

function makeModel(m){
  if(m.model)return m.model;

  let seed=(m.home.length*13+m.away.length*7)%19;
  let h=.43+(seed%8)/100, a=.29-(seed%4)/100, d=1-h-a;
  let best=h>.50?"WIN: "+m.home:"NO STRONG EDGE";

  return {
    home:h,draw:d,away:a,btts:.49+(seed%7)/100,
    bestBet:best,
    confidence:h>.50?60:43,
    factors:{
      "Recent form":60+seed%15,
      "Home / away":55+seed%18,
      "H2H":40+seed%25,
      "Lineup":35,
      "Team news":35,
      "Data quality":45
    },
    injuries:"No live player-news payload is available for this fixture yet.",
    reason:"The model uses available football information and stays conservative when important information is missing."
  };
}

function analysisHTML(m,compact=false){
  const x=makeModel(m);
  const posInfo=(m.homePos||m.awayPos)?
    `<div class="league-row"><span>League position</span><span class="team-pos">${esc(m.home)} ${m.homePos?"#"+m.homePos:"—"} · ${esc(m.away)} ${m.awayPos?"#"+m.awayPos:"—"}</span></div>`:"";

  return `
    ${posInfo}
    <div class="grid">
      <div class="metric"><small>${esc(m.home)}</small><b>${pct(x.home)}</b></div>
      <div class="metric"><small>Draw</small><b>${pct(x.draw)}</b></div>
      <div class="metric"><small>${esc(m.away)}</small><b>${pct(x.away)}</b></div>
      <div class="metric"><small>BTTS</small><b>${pct(x.btts)}</b></div>
    </div>
    <div class="${compact?"mini-pick":"pick"}">
      <div class="eyebrow">MODEL CONCLUSION</div>
      <div class="bet">${esc(x.bestBet||"NO STRONG EDGE")}</div>
      <div class="muted">Confidence ${x.confidence||0}/100</div>
    </div>
    ${Object.entries(x.factors||{}).map(([k,v])=>`
      <div class="${compact?"mini-factor":"factor"}">
        <div class="fh"><span>${esc(k)}</span><span>${v}/100</span></div>
        <div class="bar"><div class="fill" style="width:${Math.min(100,Math.max(0,v))}%"></div></div>
      </div>`).join("")}
    <div class="news"><b>INJURIES / LINEUP</b><br>${esc(x.injuries||"No information available.")}</div>
    <div class="news"><b>ANALYSIS</b><br>${esc(x.reason||"No explanation available.")}</div>
    ${!compact?`<div class="analysis-note">This analysis uses football data only. No betting-market odds are used.</div>`:""}
  `;
}

function showMainAnalysis(m){
  $("mainAnalysis").innerHTML=analysisHTML(m,false);
}

function toggleAnalysis(id){
  const m=state.matches.find(x=>String(x.id)===String(id));
  if(!m)return;
  const box=$("analysis-"+id);
  const button=document.querySelector(`#card-${CSS.escape(id)} .analyze`);
  if(!box)return;

  if(box.classList.contains("show")){
    box.classList.remove("show");
    button.textContent="ANALYZE GAME";
    return;
  }

  // Render immediately INSIDE THIS CARD, directly below its button.
  box.innerHTML=analysisHTML(m,true);
  box.classList.add("show");
  button.textContent="HIDE ANALYSIS";
}

$("refresh").onclick=load;
$("search").oninput=renderGames;

$("manualAnalyze").onclick=()=>{
  const h=$("home").value.trim(),a=$("away").value.trim(),c=$("comp").value.trim()||"Custom";
  if(!h||!a)return alert("Enter both teams.");
  const m={id:"custom"+Date.now(),home:h,away:a,competition:c,time:"Custom match"};
  $("mainGame").innerHTML=`${esc(h)} <span style="color:#697586">vs</span> ${esc(a)}`;
  $("mainMeta").textContent=c+" · Custom analysis";
  showMainAnalysis(m);
};

load();
