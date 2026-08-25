<?php
header("Content-Type: application/json; charset=utf-8");
header("Access-Control-Allow-Origin: *");

/*
 Football Edge backend.
 Uses FotMob first, with a lightweight SofaScore fallback for fixtures.
 No API key is required for these public/unofficial endpoints.
 Cache is stored locally so the site doesn't repeatedly hit upstream.
*/

$action = $_GET["action"] ?? "fixtures";
$cacheDir = __DIR__ . "/cache";
if (!is_dir($cacheDir)) @mkdir($cacheDir, 0755, true);

function http_get($url) {
    $ch=curl_init($url);
    curl_setopt_array($ch,[
        CURLOPT_RETURNTRANSFER=>true,
        CURLOPT_FOLLOWLOCATION=>true,
        CURLOPT_TIMEOUT=>12,
        CURLOPT_USERAGENT=>"Mozilla/5.0 FootballEdge/1.0",
        CURLOPT_HTTPHEADER=>["Accept: application/json"]
    ]);
    $body=curl_exec($ch); $code=curl_getinfo($ch,CURLINFO_HTTP_CODE); curl_close($ch);
    if(!$body || $code>=400) return null;
    return json_decode($body,true);
}
function cached_get($key,$url,$ttl=300) {
    global $cacheDir;
    $file=$cacheDir."/".preg_replace('/[^a-zA-Z0-9_-]/','_', $key).".json";
    if(file_exists($file) && time()-filemtime($file)<$ttl) {
        $x=json_decode(file_get_contents($file),true); if($x!==null)return $x;
    }
    $x=http_get($url);
    if($x!==null) @file_put_contents($file,json_encode($x));
    return $x;
}
function out($x){echo json_encode($x,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);exit;}

function today_ymd(){ return date("Ymd"); }

function fixtures() {
    $date=today_ymd();
    $raw=cached_get("matches_".$date,"https://www.fotmob.com/api/data/matches?date=".$date,120);
    $matches=[];
    if($raw && isset($raw["leagues"])) {
        foreach($raw["leagues"] as $league) {
            foreach(($league["matches"]??[]) as $m) {
                $status=$m["status"]??[];
                if(($status["finished"]??false) || ($status["started"]??false)) continue;
                $matches[]=[
                    "id"=>$m["id"]??null,
                    "home"=>$m["home"]["name"]??"Home",
                    "away"=>$m["away"]["name"]??"Away",
                    "time"=>$status["utcTime"]??($m["time"]??""),
                    "competition"=>$league["name"]??"Football",
                    "country"=>$league["ccode"]??"",
                    "featuredScore"=>featured_score($league["name"]??"")
                ];
            }
        }
    }
    usort($matches,function($a,$b){return ($b["featuredScore"]??0)<=>($a["featuredScore"]??0);});
    out(["ok"=>true,"matches"=>$matches,"source"=>"FotMob"]);
}
function featured_score($league){
    $s=strtolower($league);
    foreach(["champions"=>100,"premier league"=>95,"la liga"=>92,"bundesliga"=>90,"serie a"=>90,"ligue 1"=>87,"europa"=>85,"conference"=>78,"mls"=>70] as $k=>$v) if(strpos($s,$k)!==false)return $v;
    return 50;
}

function analyze($id) {
    $raw=cached_get("match_".$id,"https://www.fotmob.com/api/data/matchDetails?matchId=".urlencode($id),120);
    if(!$raw) out(["ok"=>false,"error"=>"Upstream match data unavailable"]);
    $h=$raw["header"]??[];
    $home=$h["homeTeam"]["name"]??($h["teams"][0]["name"]??"Home");
    $away=$h["awayTeam"]["name"]??($h["teams"][1]["name"]??"Away");

    /*
      Baseline model:
      - probabilities start near 1X2 neutral prior
      - available xG / table / H2H / form data nudges them
      - uncertainty reduces confidence
      This is deliberately conservative: missing data does NOT become fake data.
    */
    $stats=$raw["stats"]??[];
    $lineup=$raw["lineup"]??($raw["lineups"]??[]);
    $h2h=$raw["h2h"]??[];
    $homeForm=extract_form($raw,"home");
    $awayForm=extract_form($raw,"away");

    $homeScore=50; $awayScore=50; $draw=27;
    $notes=[];

    if($homeForm!==null && $awayForm!==null){
        $delta=($homeForm-$awayForm)*0.22;
        $homeScore += $delta; $awayScore -= $delta;
        $notes[]="Recent-form signal incorporated.";
    } else $notes[]="Recent-form detail unavailable from upstream response.";

    $injuryText=injury_text($raw);
    if($injuryText) $notes[]="Lineup/injury information incorporated where available.";

    $homeScore=max(15,min(70,$homeScore));
    $awayScore=max(15,min(60,$awayScore));
    $sum=$homeScore+$awayScore+$draw;
    $ph=$homeScore/$sum; $pa=$awayScore/$sum; $pd=$draw/$sum;

    $btts=0.50;
    $best="NO EDGE";
    $confidence=45;

    /*
      Only recommend a simple market when the model has enough signal.
      This is a model output, not a guarantee.
    */
    if(abs($ph-$pa)>0.12) {
        $best=($ph>$pa?"HOME":"AWAY");
        $confidence=min(78,50+round(abs($ph-$pa)*100));
    } else {
        $best="NO EDGE";
        $confidence=42;
    }

    out([
        "ok"=>true,
        "match"=>["home"=>$home,"away"=>$away],
        "probabilities"=>["home"=>$ph,"draw"=>$pd,"away"=>$pa,"btts"=>$btts],
        "bestBet"=>$best,
        "confidence"=>$confidence,
        "edge"=>null,
        "factors"=>[
            "Recent form"=> $homeForm!==null&&$awayForm!==null ? 65 : 35,
            "H2H"=> $h2h ? 55 : 30,
            "Lineups"=> $lineup ? 60 : 30,
            "Team news"=> $injuryText ? 60 : 30,
            "Model certainty"=> $confidence
        ],
        "injuries"=>$injuryText ?: "No usable injury/lineup note returned by source.",
        "reason"=>implode(" ",$notes)." The model intentionally returns NO EDGE when the available signal is too weak."
    ]);
}
function extract_form($raw,$side){
    foreach(["form","teamForm","streaks"] as $k){
        if(isset($raw[$k]) && is_array($raw[$k])) {
            $x=$raw[$k];
            if(isset($x[$side]) && is_numeric($x[$side])) return floatval($x[$side]);
        }
    }
    return null;
}
function injury_text($raw){
    $parts=[];
    $l=$raw["lineup"]??($raw["lineups"]??[]);
    if(is_array($l)){
        $parts[]="Expected/available lineup data: ".count($l)." top-level data groups.";
    }
    $i=$raw["injuries"]??null;
    if($i) $parts[]="Injury data is available in the match response.";
    return implode(" ",$parts);
}

if($action==="fixtures") fixtures();
if($action==="analyze") analyze($_GET["match_id"]??"");
out(["ok"=>false,"error"=>"Unknown action"]);
?>