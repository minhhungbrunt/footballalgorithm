# Football Edge — Professional GitHub Pages Build

**Fixture source: FotMob.**

This is a GitHub Pages matchday dashboard. GitHub Actions fetches the full daily FotMob feed every 15 minutes and writes `data/fixtures.json`; GitHub Pages serves the static UI.

## Included competitions
Premier League · LaLiga · Bundesliga · Serie A · Ligue 1 · Eredivisie · Primeira Liga

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
