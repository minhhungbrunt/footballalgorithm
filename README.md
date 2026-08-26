# FootballEdge

FotMob-powered football matchday dashboard.

Commit to `main`, then run **Actions → FootballEdge refresh** once. GitHub Pages must use **GitHub Actions** as its publishing source.

The site polls its local feed every 30 seconds and attempts a direct FotMob live-score heartbeat every 5 seconds while matches are live.


## FAST PATCH
The updater uses FotMob /api/data routes first, 5 concurrent workers, 10s request timeout, and prints progress. The static GitHub Pages frontend polls the feed every 30s and attempts live score polling every 5s. GitHub Actions itself cannot run every 5 seconds.
