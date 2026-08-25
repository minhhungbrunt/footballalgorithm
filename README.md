# FOOTBALL EDGE — FRONT PAGE / DATA PIPELINE PATCH

This build is the corrected front-end + data pipeline. It is **not** a seed-only UI.

# Football Edge — Professional GitHub Pages Build

**Fixture source: FotMob.**

This is a GitHub Pages matchday dashboard. GitHub Actions fetches the full daily FotMob feed every 15 minutes and writes `data/fixtures.json`; GitHub Pages serves the static UI.

## Included competitions
30 competition filters are included, covering:
- Premier League, Championship, League One
- LaLiga, LaLiga 2, Copa del Rey
- Bundesliga, 2. Bundesliga, DFB Pokal
- Serie A, Serie B, Coppa Italia
- Ligue 1, Ligue 2, Coupe de France
- Eredivisie, Eerste Divisie
- Primeira Liga, Liga Portugal 2
- FA Cup, EFL Cup
- UEFA Champions League + Champions League Qualification, Europa League + Qualification, Conference League + Qualification
- Scottish Premiership
- Belgian Pro League
- Turkish Super Lig
- Saudi Pro League
- MLS
- Brasileirão
- Liga MX

The updater canonicalizes FotMob's `primaryId` first and then falls back to competition-name aliases. This prevents a Premier League match from being mislabeled when FotMob changes the display wording.

Major cup/European fixtures from FotMob's daily feed are also retained.

## UI
- Matchday-style fixture list
- Many fixtures, grouped by league
- League position
- Main-game spotlight
- Search and sorting
- Analyze button directly inside each match row
- Actual team names
- Compact professional dark UI
- No manual team entry
- No Kalshi/bookmaker odds

## Model
Each match produces a concrete decision:
- WIN: Team
- DRAW
- probability for each result
- confidence
- projected score
- BTTS probability
- factors: form, table, home/away, H2H, xG, availability

Missing player information is not invented. The next data layer can fetch FotMob match details by match ID for richer form/xG/H2H/lineup/injury inputs.

## GitHub setup
Put these at the repository root:

```text
index.html
app.js
style.css
data/fixtures.json
scripts/update.py
.github/workflows/update-data.yml
.github/workflows/pages.yml
.nojekyll
```

Settings → Pages → **GitHub Actions**

Then run:
**Actions → Football Edge — Update Matchday → Run workflow**

The update workflow runs every 15 minutes.

`update-data.yml` will NOT replace a working fixture file with an empty/broken response.

`pages.yml` deploys the site after commits to `main`.

No private API key is placed in browser JavaScript.


## If you see "Waiting for GitHub Action"

That is intentional for a brand-new repository: the repository no longer ships fake fixtures.

Run:

**Actions → Football Edge — Update Matchday → Run workflow**

The updater uses FotMob's daily matches endpoint:

`https://www.fotmob.com/api/matches?date=YYYYMMDD`

FotMob's documented daily response is grouped by league and contains all matches for that date. citeturn0search2

After the Action commits `data/fixtures.json`, GitHub Pages deploys the real matchday automatically.


### Competition source
FotMob's daily matches response includes `primaryId`, league name and the full list of matches; the updater uses that structure instead of assuming the first league or first match is Premier League. See the FotMob API documentation for the daily matches and league-directory structures.


### Cup division handling
For cup and European fixtures, the displayed **Competition** is the match competition (for example EFL Cup), but **Current division** comes from each team's primary domestic league/table via FotMob's team endpoint. A cup name is never used as a club's division or strength tier. The cache is versioned so older misclassified team data is discarded on the next Action run.


## Model V3 — evidence-driven
The updater hydrates upcoming/live matches with FotMob `matchDetails`, including available xG, lineup status, starting-player counts/ratings, and H2H fields when FotMob supplies them. It also samples each team's recent results from the FotMob team feed. The frontend model then combines:
1. current domestic division strength;
2. current domestic table position;
3. last-five form;
4. available lineup quality/availability;
5. limited H2H;
6. a small home-field adjustment.

A cup's competition is never used as the team's domestic division. Missing data is shown as unavailable rather than fabricated.

FotMob documents `matches` as the daily fixture feed and `matchDetails` as the comprehensive endpoint for lineups, xG and match statistics. citeturn2view0

## Deep analysis V4
The match analyzer now combines:
- FotMob match details: lineups, formations, player ratings, xG, H2H and availability when supplied.
- RotoWire predicted/confirmed lineup supplement for supported leagues, matched by both team names.
- Current domestic division and table position for cup/European ties.
- Last-five team form from FotMob team fixtures.
- Starting-XI quality from FotMob match ratings.
- Player season rating and transfer value when FotMob exposes them; these are secondary signals, not the main driver.
- Player-weighted lineup/availability evidence and a data-completeness score.

RotoWire lineup pages provide predicted/confirmed XIs, formations and injury/team-news information; FotMob provides predicted lineups before matches and confirmed lineups around kickoff, plus player ratings and match analytics.

The site does not use bookmaker or Kalshi odds in the model.

## Automatic updates / troubleshooting
The fixture updater is scheduled every 15 minutes at minutes 7, 22, 37 and 52 UTC. A separate weekly heartbeat makes a repository commit so a public repository does not sit inactive long enough for GitHub to disable scheduled workflows. GitHub documents that scheduled workflows can be automatically disabled in public repositories after 60 days without repository activity. 

If the site stops changing, open **Actions → Football Edge — Update Matchday** and inspect the latest run. The workflow now fails loudly if FotMob produces zero accepted fixtures instead of silently publishing an empty dataset.

## Automatic FotMob refresh
The updater runs automatically every 15 minutes at :07, :22, :37 and :52 UTC. It retries transient FotMob failures, prints the accepted fixture count, and refuses to publish an empty dataset. A weekly heartbeat commit helps keep a public repository active because GitHub can automatically disable scheduled workflows after 60 days without repository activity. See GitHub's workflow documentation for scheduled events and workflow disabling.

If the Actions tab shows no runs at all, check **Settings → Actions → General** and make sure Actions are allowed, then open the workflow and choose **Enable workflow** if GitHub has disabled it. The first manual run is only a diagnostic/test; future runs are scheduled.

### Data-source caveat
FotMob's public website currently displays a notice that automated services/robots are not permitted. The project therefore treats FotMob as a best-effort source; if FotMob blocks GitHub's runner, the workflow will fail visibly instead of silently serving stale or fake fixtures. For a production/public application, use a licensed/supported football-data API.


## Competition classification fix
The updater no longer uses numeric FotMob league IDs as the classifier. Domestic competitions are matched by competition name **and country**. This prevents a club in Kuwait/Azerbaijan/etc. from being labeled as the English Premier League simply because its local competition is also called “Premier League”. UEFA qualification stages are explicitly accepted and displayed separately.

## V5 data behavior
- FotMob is the primary fixture, match-detail and player-data source.
- If FotMob returns no accepted fixtures, the updater falls back to ESPN's public scoreboard feed so the page does not stay blank.
- Live/finished scores are cross-checked against the fallback feed and displayed on the front page.
- The browser reloads `data/fixtures.json` every 60 seconds; GitHub Actions is still responsible for fetching fresh data.
- The Analyze panel shows the concrete verdict, probabilities, deep evidence narrative and RotoWire XI listing. The old factor-score grid has been removed.


## V6 model behavior
The model treats **Draw as a first-class outcome**. It does not always select a team.
It combines division strength, same-division table position, last-five form, goals for/against,
lineup/season rating, squad value as a secondary signal, availability, xG, H2H and a small home
advantage. Cross-division fixtures never compare raw league positions across divisions.
Missing data lowers confidence instead of creating synthetic evidence.
