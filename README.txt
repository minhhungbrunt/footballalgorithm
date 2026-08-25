FOOTBALL EDGE — INFINITYFREE SETUP

FILES
-----
index.html
api.php
cache/   (create this folder)

UPLOAD
------
Upload index.html and api.php into public_html on InfinityFree.
Create an empty folder named "cache" inside public_html.

REQUIREMENTS
------------
PHP with cURL enabled.

IMPORTANT
---------
This version uses public/unofficial FotMob endpoints server-side.
Those endpoints can change or rate-limit requests. The backend caches
responses to reduce requests.

The current model is a SAFE STARTER MODEL, not a production betting
model. It deliberately returns NO EDGE when it lacks enough information.

NEXT MODEL UPGRADES
-------------------
1. Team recent results from team/league endpoints
2. Home/away splits
3. H2H last 5/10
4. xG for/against
5. injuries and suspensions by player
6. expected XI vs confirmed XI
7. player minutes/availability
8. rest days
9. competition importance
10. market price comparison
11. closing-line tracking
12. backtesting

KALSHI
------
Do not put a Kalshi secret/API credential in index.html.
If you later connect a market-data API, keep credentials in api.php
or a server environment variable.

DISCLAIMER
----------
Predictions are statistical estimates and are not guaranteed outcomes.
