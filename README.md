# FootballEdge V7

This is a GitHub Pages site with a GitHub Actions data pipeline.

## What this fixes
- Draw is a genuine 1X2 outcome.
- No default home-team prediction.
- Cross-division matches do not compare raw table positions.
- Premier League is not matched by the string "Premier League" alone; competition country is considered.
- UCL and UCL qualification are explicit competitions.
- Live/FT scores are shown.
- Analysis opens inside the selected match row.
- RotoWire is used as the lineup/injury listing for supported competitions; the UI is text-only.
- FotMob is the primary fixture/match-detail source.
- Missing data lowers confidence instead of generating fake evidence.

## GitHub Pages
Settings → Pages → Source: GitHub Actions.

## First run
Actions → Update FootballEdge data → Run workflow.

After that the workflow runs every 15 minutes and commits `data/fixtures.json`.
The Pages workflow redeploys after that commit.

## Important
Do not use a PHP/API proxy. This project is GitHub Pages + GitHub Actions only.

## Data used by the model
FotMob match details are used for match state, xG where available, lineups/player ratings where exposed, and match context. RotoWire is separately queried for its text lineup/injury listing. Player market value is secondary and never determines the verdict by itself.
