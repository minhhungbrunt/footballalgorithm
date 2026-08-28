# FootballEdge

FotMob-powered football matchday dashboard.

Commit to `main`, then run **Actions → FootballEdge refresh** once. The site checks the published feed every 30 seconds; the Action refreshes the feed on its schedule.



## V13 data pipeline fix
The updater keeps the working daily FotMob fixture feed, but no longer depends on the retired `/api/teams` and `/api/matchDetails` routes for enrichment. Team/match/league pages are read from server-rendered `__NEXT_DATA__`; recent domestic form is reconstructed from the working daily fixture feed. The workflow refuses to publish fallback-only data when form/division enrichment is zero.

## V14 machine-learning prediction layer
The updater now trains a leakage-safe 1X2 ML ensemble from completed historical fixtures. It combines logistic regression with a random forest and blends the learned probabilities with the existing Poisson/Dixon-Coles model rather than replacing it outright. The model is retrained at most every 12 hours and persisted as `data/ml_model.joblib`, so the normal 5-minute fixture refresh does not retrain it. The generated feed records ML training rows and holdout accuracy/log-loss in `mlModel`.

The training features are pre-match only: team Elo difference, recent form, recent goal difference, draw tendency, league-strength environment, same-division indicator, home advantage, and experience. No post-match score/xG is used to predict an upcoming match.
