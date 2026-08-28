"""FootballEdge ML layer.

A leakage-safe multiclass model trained only on completed matches.  The model is
an ensemble of logistic regression (stable/calibrated) and random forest
(non-linear interactions).  A compact joblib artifact is persisted so the
5-minute refresh does not retrain on every run.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path
from collections import defaultdict, deque

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

VERSION = 1
MAX_ARTIFACT_AGE_HOURS = 12
FEATURES = [
    "elo_diff", "form_diff", "goal_diff", "draw_rate_diff",
    "league_strength", "league_draw_rate", "same_division", "home_advantage", "experience_diff",
]


def _num(x, default=0.0):
    try: return float(x)
    except (TypeError, ValueError): return default


def _result(hs, aas):
    return 0 if hs > aas else 1 if hs == aas else 2


def _is_usable_row(m, status_fn, score_fn):
    if not isinstance(m, dict) or status_fn(m) != "FT":
        return False
    h, a = m.get("home") or {}, m.get("away") or {}
    if h.get("id") is None or a.get("id") is None:
        return False
    hs, aas = score_fn(m)
    return hs is not None and aas is not None


def _state(team=None):
    return {
        "elo": 1500.0,
        "games": 0,
        "gf": 0.0,
        "ga": 0.0,
        "recent": deque(maxlen=5),
        "draws": deque(maxlen=20),
    }


def _feature_from_states(h, a, league_strength=1600.0, league_draw_rate=0.30):
    hp = sum(3 if x == 0 else 1 if x == 1 else 0 for x in h["recent"])
    ap = sum(3 if x == 0 else 1 if x == 1 else 0 for x in a["recent"])
    hgd = (h["gf"] - h["ga"]) / max(1, h["games"])
    agd = (a["gf"] - a["ga"]) / max(1, a["games"])
    hdr = sum(h["draws"]) / max(1, len(h["draws"]))
    adr = sum(a["draws"]) / max(1, len(a["draws"]))
    return [
        (h["elo"] - a["elo"]) / 400.0,
        (hp - ap) / 15.0,
        (hgd - agd) / 5.0,
        hdr - adr,
        (league_strength - 1600.0) / 300.0,
        league_draw_rate - 0.30,
        1.0,
        1.0,
        (h["games"] - a["games"]) / 20.0,
    ]


def _update_elo(h, a, outcome, k=24.0):
    expected = 1.0 / (1.0 + 10 ** ((a["elo"] - h["elo"]) / 400.0))
    actual = 1.0 if outcome == 0 else 0.5 if outcome == 1 else 0.0
    change = k * (actual - expected)
    h["elo"] += change
    a["elo"] -= change


def build_training(rows, status_fn, score_fn, league_strength_fn, supported_fn=None):
    rows = sorted(rows, key=lambda m: str((m.get("status") or {}).get("utcTime") or m.get("utcTime") or ""))
    states = defaultdict(_state)
    league_stats = defaultdict(lambda: [0, 0])  # games, draws
    X, y = [], []
    used = 0

    for m in rows:
        if not _is_usable_row(m, status_fn, score_fn):
            continue
        comp = str(m.get("_league_name") or m.get("competition") or "")
        country = str(m.get("_country") or m.get("competitionCountry") or "")
        if supported_fn and not supported_fn(comp, country):
            continue
        h = m.get("home") or {}; a = m.get("away") or {}
        hid, aid = str(h.get("id")), str(a.get("id"))
        hs, aas = score_fn(m); hs, aas = int(hs), int(aas)
        outcome = _result(hs, aas)
        hk = (country, comp)
        lg = league_stats[hk]
        league_rate = lg[1] / lg[0] if lg[0] else 0.30
        # League strength is a prior; it is not the label and cannot leak the result.
        lstrength = _num(league_strength_fn(comp if comp else ""), 1600.0)
        X.append(_feature_from_states(states[hid], states[aid], lstrength, league_rate))
        y.append(outcome)
        used += 1

        _update_elo(states[hid], states[aid], outcome)
        hh, aa = states[hid], states[aid]
        hh["games"] += 1; aa["games"] += 1
        hh["gf"] += hs; hh["ga"] += aas
        aa["gf"] += aas; aa["ga"] += hs
        hh["recent"].append(outcome); aa["recent"].append(2 if outcome == 0 else 1 if outcome == 1 else 0)
        hh["draws"].append(1 if outcome == 1 else 0); aa["draws"].append(1 if outcome == 1 else 0)
        lg[0] += 1; lg[1] += 1 if outcome == 1 else 0

    return np.asarray(X, dtype=float), np.asarray(y, dtype=int), states, used


def train(X, y):
    if len(X) < 120 or len(set(y.tolist())) < 3:
        raise ValueError(f"not enough ML history: {len(X)} rows / {len(set(y.tolist())) if len(y) else 0} classes")
    split = max(80, int(len(X) * 0.80))
    if split >= len(X) - 20: split = len(X) - 20
    Xtr, Xte, ytr, yte = X[:split], X[split:], y[:split], y[split:]

    lr = Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
    ])
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=7, min_samples_leaf=8,
        class_weight="balanced_subsample", random_state=42, n_jobs=-1,
    )
    lr.fit(Xtr, ytr); rf.fit(Xtr, ytr)
    p1 = lr.predict_proba(Xte); p2 = rf.predict_proba(Xte)
    # Stable model gets slightly more weight; RF handles non-linear interactions.
    p = 0.60 * p1 + 0.40 * p2
    metrics = {
        "holdout_accuracy": round(float(accuracy_score(yte, np.argmax(p, axis=1))), 4),
        "holdout_logloss": round(float(log_loss(yte, p, labels=[0,1,2])), 4),
        "holdout_rows": int(len(yte)),
        "class_counts": [int((y == i).sum()) for i in range(3)],
    }
    return lr, rf, metrics


def load_if_fresh(path, now=None):
    path=Path(path); now=now or dt.datetime.now(dt.timezone.utc)
    if not path.exists(): return None
    try:
        art=joblib.load(path)
        created=dt.datetime.fromisoformat(art.get("createdAt", "").replace("Z", "+00:00"))
        if art.get("version") != VERSION: return None
        age=(now-created).total_seconds()/3600
        return art if age < MAX_ARTIFACT_AGE_HOURS else None
    except Exception:
        return None

def train_or_load(path, rows, status_fn, score_fn, league_strength_fn, supported_fn=None, now=None):
    path = Path(path)
    now = now or dt.datetime.now(dt.timezone.utc)
    if path.exists():
        try:
            art = joblib.load(path)
            created = dt.datetime.fromisoformat(art.get("createdAt", "").replace("Z", "+00:00"))
            age = (now - created).total_seconds() / 3600
            if art.get("version") == VERSION and age < MAX_ARTIFACT_AGE_HOURS:
                return art, False
        except Exception:
            pass

    X, y, states, used = build_training(rows, status_fn, score_fn, league_strength_fn, supported_fn)
    lr, rf, metrics = train(X, y)
    serial_states = {}
    for tid, s in states.items():
        serial_states[tid] = {
            "elo": s["elo"], "games": s["games"], "gf": s["gf"], "ga": s["ga"],
            "recent": list(s["recent"]), "draws": list(s["draws"]),
        }
    art = {
        "version": VERSION,
        "createdAt": now.isoformat(),
        "features": FEATURES,
        "lr": lr,
        "rf": rf,
        "states": serial_states,
        "trainingRows": int(used),
        "metrics": metrics,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(art, path, compress=3)
    return art, True


def _current_state(art, team, fallback_form=""):
    tid=str((team or {}).get("id"))
    raw=art.get("states",{}).get(tid)
    if raw:
        s={"elo":_num(raw.get("elo"),1500),"games":int(raw.get("games") or 0),"gf":_num(raw.get("gf")),"ga":_num(raw.get("ga")),"recent":deque(raw.get("recent",[]),maxlen=5),"draws":deque(raw.get("draws",[]),maxlen=20)}
    else:
        s=_state(team)
    # Current feed is newer than the training snapshot; merge the visible last-5 form.
    form=str((team or {}).get("form") or fallback_form or "")[-5:]
    if form:
        conv=[0 if c=="W" else 1 if c=="D" else 2 for c in form]
        s["recent"]=deque(conv,maxlen=5)
        s["draws"]=deque([1 if c=="D" else 0 for c in form],maxlen=20)
    return s


def predict(art, match, league_strength_fn):
    if not art: return None
    h=match.get("homeData") or {}; a=match.get("awayData") or {}
    hs=_current_state(art,h); aas=_current_state(art,a)
    same=1.0 if h.get("division") and h.get("division")==a.get("division") else 0.0
    lstrength=_num(league_strength_fn(match.get("competition") or h.get("division")),1600.0)
    x=np.asarray([_feature_from_states(hs,aas,lstrength,0.30)[:6] + [same,1.0, (hs["games"]-aas["games"])/20.0]],dtype=float)
    # Feature ordering is [elo, form, gd, draw, league, same, home, experience].
    p1=art["lr"].predict_proba(x)[0]
    p2=art["rf"].predict_proba(x)[0]
    p=0.60*p1+0.40*p2
    p=np.clip(p,0.001,0.998); p=p/p.sum()
    return [float(v) for v in p]
