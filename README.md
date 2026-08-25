# Football Edge — GitHub Pages

This version is specifically for **GitHub Pages**.

It contains only static files:
- `index.html`
- `style.css`
- `app.js`
- `.nojekyll`

There is **no PHP** and no InfinityFree/server requirement.

## Install

Upload all files to the root of your GitHub repository.

For a user site, the repository should be:

`YOUR-USERNAME.github.io`

GitHub Pages can publish static HTML/CSS/JavaScript directly from a repository.

Go to:

**Settings → Pages → Build and deployment → Source**

Choose **Deploy from a branch**, then select:

`main` / `/ (root)`

## Important data behavior

The site tries to load today's fixtures from FotMob directly in the browser.

Some public endpoints may reject browser cross-origin requests. If that happens, the site automatically switches to **Demo Fallback** instead of showing a broken page.

The proper production architecture for unrestricted live data is:

GitHub Pages
→ Cloudflare Worker / other serverless proxy
→ SofaScore/FotMob
→ model
→ GitHub Pages

Do NOT put private API keys in `app.js` or `index.html`.

## Model

The starter model intentionally does not invent missing injuries, lineups or H2H data.

The next production layer should add:
- rolling last-5/10 form
- home/away splits
- xG for/against
- H2H last 5/10
- injuries and suspensions
- expected XI
- confirmed XI
- player importance/minutes
- rest days
- competition context
- Kalshi contract price
- model probability vs market probability
- edge
- backtesting
- NO BET threshold
