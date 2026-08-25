# Football Edge — Current Matchday

This is the **GitHub Pages + GitHub Actions** version.

## What it does

Every 15 minutes, GitHub Actions fetches the current day's FotMob fixture feed, keeps all active fixtures from the seven selected top leagues, and — when that set is small on a weekday — supplements the page with major European/domestic cup fixtures. It does **not** truncate the result to one game.

The seven primary leagues are:

- Premier League
- LaLiga
- Bundesliga
- Serie A
- Ligue 1
- Eredivisie
- Primeira Liga

Supplemental competitions include Champions League, Europa League, Conference League and major domestic cups when needed to make the matchday useful.

FotMob's documented daily match route returns fixtures grouped by league, and the match ID can be used with its match-details endpoint for xG, lineups, stats and other analysis data. citeturn1view0turn1view1

## Important fix from v4

The old workflow relied on `lg.id`. Some FotMob responses expose the league identifier as `primaryId`. The updater now accepts both and also identifies the seven leagues by their names. This prevents the updater from silently dropping most leagues.

## Automatic update

`.github/workflows/update-data.yml` runs:

`*/15 * * * *`

It writes the current matchday to:

`data/fixtures.json`

Then GitHub Pages reads that JSON.

GitHub scheduled workflows are not guaranteed to start exactly on the minute, but GitHub will run the workflow on its schedule when the Actions service is available.

## Analysis model

The current pre-match model is intentionally transparent:

- league position
- home/away context
- recent-form availability
- H2H availability
- team-news availability
- data quality

It outputs a probability distribution and can say `NO STRONG EDGE` rather than forcing a selection.

**No Kalshi or bookmaker odds are used.**

The next model layer should fetch match details and team histories for each selected fixture and calculate actual:

- last 5 / last 10 form
- goals for/against
- xG for/against
- home/away splits
- H2H last 5/10
- injuries/suspensions
- expected XI
- confirmed XI
- player ratings/importance
- rest days
- competition context

Those values can then feed a weighted or calibrated model before the UI displays the conclusion.
