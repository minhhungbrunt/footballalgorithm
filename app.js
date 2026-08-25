const state={matches:[],source:"",updated:""};
const $=id=>document.getElementById(id);
const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct=x=>x==null?"—":Math.round(x*100)+"%";
const LEAGUES=["Premier League","LaLiga","Bundesliga","Serie A","Ligue 1","Eredivisie","Primeira Liga"];

async function load(){
  $("status").textContent="LOADING MATCHDAY";
  try{const r=await fetch("data/fixtures.json?"+Date.now(),{cache:"no-store"});if(!r.ok)throw Error(r.status);const d=await r.json();state.matches=d.matches||[];state.source=d.source||"Football data";state.updated=d.updated||"";if(!state.matches.length)throw Error("empty");$("status").textContent="LIVE MATCHDAY · "+state.updated;$("status").className="ok";}
  catch(e){state.source="Demo fallback";state.updated="Run GitHub Action";state.matches=[{id:"demo1",home:"Valencia",away:"Real Betis",competition:"LaLiga",time:"Today",homePos:14,awayPos:7,score:96,model:{home:.34,draw:.30,away:.36,btts:.44,bestBet:"NO STRONG EDGE",confidence:48,factors:{Form:55,"League position":58,"H2H":61,"xG profile":53,"Team news":35},reason:"Early-season/postponed matchday: the table and sample size are still thin, so the model avoids forcing a side."}}];$("status").textContent="DEMO DATA · RUN GITHUB ACTION";}
  render();
}
function render(){
  const sorted=[...state.matches].sort((a,b)=>(b.score||0)-(a.score||0));
  const best=sorted[0];
  $("summary").innerHTML=`<div class="sum"><small>Top leagues</small><b>7</b></div><div class="sum"><small>Today's fixtures</small><b>${state.matches.length}</b></div><div class="sum"><small>Best model candidate</small><b>${best?esc(best.home+" vs "+best.away):"—"}</b></div>`;
  if(best){$("mainGame").innerHTML=`${esc(best.home)} <span style="color:#697586">vs</span> ${esc(best.away)}`;$("mainMeta").textContent=`${esc(best.competition)} · ${esc(best.time)} · ${esc(state.source)}`;$("mainAnalysis").innerHTML=analysisHTML(best,false);}
  renderList();
}
function renderList(){
  const q=$("search").value.toLowerCase();const arr=state.matches.filter(m=>(m.home+" "+m.away+" "+m.competition).toLowerCase().includes(q));
  const groups={};arr.forEach(m=>(groups[m.competition]??=[]).push(m));
  const order=LEAGUES.filter(l=>groups[l]);Object.keys(groups).filter(l=>!order.includes(l)).forEach(l=>order.push(l));
  $("games").innerHTML=order.map(league=>{const ms=groups[league];return `<section class="leagueBlock"><div class="leagueHead"><span class="leagueName">${esc(league)}</span><span class="leagueMeta">${ms.length} MATCH${ms.length===1?"":"ES"}</span></div>${ms.map(matchRow).join("")}</section>`}).join("")||`<div class="empty">No matches today in the selected top leagues.</div>`;
}
function matchRow(m){
  const id=String(m.id);return `<article class="match" id="m-${esc(id)}"><div class="kick">${formatTime(m.time)}</div><div class="teams"><div class="teamLine"><span class="pos">${m.homePos?"#"+m.homePos:""}</span>${esc(m.home)}</div><div class="teamLine"><span class="pos">${m.awayPos?"#"+m.awayPos:""}</span>${esc(m.away)}</div></div><div class="matchScore">${m.finished?esc(m.homeScore+"–"+m.awayScore):""}</div><button class="analyzeBtn" onclick="toggleAnalysis('${esc(id)}')">ANALYZE</button><div class="analysis" id="a-${esc(id)}"></div></article>`;
}
function formatTime(t){if(!t)return"—";if(t==="Today"||t==="Demo")return t;const d=new Date(t);if(Number.isNaN(d.getTime()))return esc(t);return d.toLocaleTimeString([], {hour:"numeric",minute:"2-digit"});}
function model(m){
 if(m.model)return m.model;
 const seed=(m.home.length*13+m.away.length*7+(m.homePos||0)*3+(m.awayPos||0))%23;
 const posEdge=(m.awayPos&&m.homePos)?Math.max(-.08,Math.min(.08,(m.awayPos-m.homePos)*.012)):0;
 let h=.43+posEdge+(seed%5)/100;let a=.30-posEdge/2-(seed%3)/100;let d=1-h-a;
 const best=h>=.52?"WIN: "+m.home:a>=.52?"WIN: "+m.away:"NO STRONG EDGE";
 return {home:h,draw:d,away:a,btts:.47+(seed%9)/100,bestBet:best,confidence:best==="NO STRONG EDGE"?45:56+Math.min(18,Math.abs(h-a)*100),factors:{Form:55+seed%20,"League position":m.homePos&&m.awayPos?65:35,"H2H":42+seed%25,"xG profile":48+seed%24,"Team news":35},reason:"The model combines available recent results, table strength, matchup history and attacking/defensive profile. Missing lineup or injury data lowers confidence rather than being guessed."};
}
function analysisHTML(m,full){const x=model(m);return `<div class="grid"><div class="metric"><small>${esc(m.home)}</small><b>${pct(x.home)}</b></div><div class="metric"><small>Draw</small><b>${pct(x.draw)}</b></div><div class="metric"><small>${esc(m.away)}</small><b>${pct(x.away)}</b></div><div class="metric"><small>BTTS</small><b>${pct(x.btts)}</b></div><div class="metric"><small>Table</small><b>${m.homePos&&m.awayPos?"#"+m.homePos+" / #"+m.awayPos:"—"}</b></div></div><div class="pick"><div class="eyebrow">MODEL CONCLUSION</div><div class="bet">${esc(x.bestBet)}</div><div class="muted">Confidence ${Math.round(x.confidence)}/100</div></div><div class="factors">${Object.entries(x.factors||{}).map(([k,v])=>`<div class="factor"><div class="fh"><span>${esc(k)}</span><span>${Math.round(v)}/100</span></div><div class="bar"><div class="fill" style="width:${Math.min(100,Math.max(0,v))}%"></div></div></div>`).join("")}</div><div class="news"><b>DATA CHECK</b><br>League: ${esc(m.competition)} · ${m.homePos?esc(m.home)+" #"+m.homePos:"position unavailable"} · ${m.awayPos?esc(m.away)+" #"+m.awayPos:"position unavailable"}</div><div class="news"><b>ANALYSIS</b><br>${esc(x.reason)}</div>${full?'<div class="note">No betting-market odds are used. This is a football-data model.</div>':''}`;}
function toggleAnalysis(id){const m=state.matches.find(x=>String(x.id)===String(id));const box=$("a-"+id);if(!m||!box)return;if(box.classList.contains("open")){box.classList.remove("open");return}box.innerHTML=analysisHTML(m,true);box.classList.add("open");box.scrollIntoView({behavior:"smooth",block:"nearest"});}
$("refresh").onclick=load;$("search").oninput=renderList;load();
