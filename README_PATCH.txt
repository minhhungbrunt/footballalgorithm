# FootballEdge — Perfect UI patch

This is a FRONT-END patch for the current GitHub Pages repository.

Replace:
- index.html
- app.js
- style.css

This removes all RotoWire UI references and makes the analysis panel FotMob-only.

Design changes:
- FotMob-style dense dark match rows
- analysis opens directly inside the selected match
- model decision is visually dominant
- 1X2 probabilities with bars
- key-factor meters
- evidence cards
- team comparison
- recent-form pills
- FotMob lineup cards
- live-score strip
- no raw "--" clutter; unavailable values become clear labels
- no invented data
- no RotoWire links or RotoWire wording
- responsive mobile layout

IMPORTANT:
This patch does not change scripts/update.py. It is intentionally safe to apply after the FotMob-only updater patch.
