# Football Edge v2 — GitHub Pages

## Why this version is different

The previous version tried to call FotMob directly from the browser. That is unreliable because browser CORS rules can block cross-origin API requests.

This version uses **GitHub Actions as the server-side fetcher**:

GitHub Actions → FotMob → `data/fixtures.json` → GitHub Pages

Cloudflare documents the same underlying issue: a browser cannot freely fetch an API that does not provide the necessary CORS headers, while a server-side proxy/worker can fetch it and return CORS-enabled data. citeturn0search0

## Upload

Put everything in the root of your GitHub repository:

- `index.html`
- `style.css`
- `app.js`
- `data/fixtures.json`
- `.github/workflows/update-data.yml`
- `.nojekyll`

## Turn on GitHub Pages

Repository → Settings → Pages

Source:
`GitHub Actions`

Then run the workflow once manually:

Actions → **Update football data** → Run workflow.

After it runs, refresh your GitHub Pages website.

The workflow is scheduled every 15 minutes.

## What you will see

The page will ALWAYS show games.

If the GitHub Action has successfully fetched current data:
`LIVE DATA · UPDATED ...`

If the data file has not been generated yet:
`DATA FILE NOT UPDATED · DEMO`

So you will no longer get the completely blank page from the previous version.

## Next step

The fixture pipeline is now separated from the frontend. That makes it possible to add a second workflow that fetches:

- last 5 / last 10 form
- H2H
- xG
- home/away splits
- injuries
- suspensions
- expected XI
- confirmed XI
- player importance
- rest days

and stores them in `data/matches/<match_id>.json`.

Then the JavaScript model can calculate:
`model probability → Kalshi price → edge → best simple contract → NO BET`

Do not put private Kalshi/API credentials in GitHub Pages JavaScript.
