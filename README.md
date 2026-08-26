# FootballEdge

FotMob-powered football matchday dashboard.

Commit to `main`, then run **Actions → FootballEdge refresh** once. The site checks the published feed every 30 seconds; the Action refreshes the feed on its schedule.



## V13 data pipeline fix
The updater keeps the working daily FotMob fixture feed, but no longer depends on the retired `/api/teams` and `/api/matchDetails` routes for enrichment. Team/match/league pages are read from server-rendered `__NEXT_DATA__`; recent domestic form is reconstructed from the working daily fixture feed. The workflow refuses to publish fallback-only data when form/division enrichment is zero.
