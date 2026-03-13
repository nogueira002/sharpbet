"""
Treino dos modelos de mercado secundários:
  - BTTS (Ambas Marcam):   SIM se home_goals > 0 E away_goals > 0
  - Over/Under 2.5 golos: OVER se home_goals + away_goals > 2.5

Usa os mesmos 43 features do modelo 1X2 (35 base + 3 Elo + 5 H2H).
Usa raw_fixtures.json (já descarregado) — 0 requests à API.

Uso:
  python -m models.train_markets
"""

import os
import json
import numpy as np
from collections import defaultdict
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.utils import compute_sample_weight
from sklearn.metrics import classification_report
import xgboost as xgb
import joblib

from models.features import build_full_features, LEAGUE_HOME_AVG, LEAGUE_AWAY_AVG
from models.elo import EloEngine
from models.h2h import H2HIndex

RAW_PATH  = os.path.join(os.path.dirname(__file__), "saved", "raw_fixtures.json")
BTTS_PATH = os.path.join(os.path.dirname(__file__), "saved", "btts_model.pkl")
OU_PATH   = os.path.join(os.path.dirname(__file__), "saved", "ou_model.pkl")

MIN_FORM = 3


# ──────────────────────────────────────────────
# Dataset
# ──────────────────────────────────────────────

def build_market_dataset():
    """
    Mesma lógica de rebuild_features mas extrai labels BTTS e Over/Under 2.5.
    Usa 43 features (35 base + 3 Elo + 5 H2H) sem data leakage.
    """
    if not os.path.exists(RAW_PATH):
        raise FileNotFoundError(
            "raw_fixtures.json nao encontrado. Corre: python -m models.collect_training_data"
        )

    with open(RAW_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    # Parse
    matches = []
    for m in raw:
        hg = m["goals"]["home"] or 0
        ag = m["goals"]["away"] or 0
        matches.append({
            "date":       m["fixture"]["date"],
            "league_id":  m["league"]["id"],
            "season":     m["league"]["season"],
            "home_id":    m["teams"]["home"]["id"],
            "away_id":    m["teams"]["away"]["id"],
            "home_name":  m["teams"]["home"]["name"],
            "away_name":  m["teams"]["away"]["name"],
            "home_goals": hg,
            "away_goals": ag,
            "winner": True if hg > ag else (False if ag > hg else None),
        })
    matches.sort(key=lambda m: m["date"])

    # Estado progressivo (Elo + H2H + forma + standings)
    elo_engine = EloEngine()
    h2h_index  = H2HIndex()
    all_hist   = defaultdict(list)
    home_hist  = defaultdict(list)
    away_hist  = defaultdict(list)
    points       = defaultdict(lambda: defaultdict(int))
    league_goals = defaultdict(lambda: {"home": 0, "away": 0, "games": 0})

    # Número de equipas por liga/época
    teams_set = defaultdict(set)
    for m in matches:
        key = (m["league_id"], m["season"])
        teams_set[key].add(m["home_id"])
        teams_set[key].add(m["away_id"])
    num_teams = {k: len(v) for k, v in teams_set.items()}

    X_list = []
    y_btts = []
    y_ou   = []

    for match in matches:
        h_id   = match["home_id"]
        a_id   = match["away_id"]
        h_name = match["home_name"]
        a_name = match["away_name"]
        hg     = match["home_goals"]
        ag     = match["away_goals"]
        key    = (match["league_id"], match["season"])
        total  = num_teams.get(key, 20)

        h_all  = list(all_hist[h_id][-10:])
        a_all  = list(all_hist[a_id][-10:])
        h_home = list(home_hist[h_id][-5:])
        a_away = list(away_hist[a_id][-5:])

        if len(h_all) >= MIN_FORM and len(a_all) >= MIN_FORM:
            pts_sorted = sorted(points[key].values(), reverse=True)

            def get_pos_norm(team_id):
                pts  = points[key].get(team_id, 0)
                rank = next((i for i, p in enumerate(pts_sorted) if p <= pts), len(pts_sorted))
                return rank / max(total - 1, 1)

            h_pos = get_pos_norm(h_id)
            a_pos = get_pos_norm(a_id)

            lg      = league_goals[key]
            lg_home = lg["home"] / lg["games"] if lg["games"] >= 5 else LEAGUE_HOME_AVG
            lg_away = lg["away"] / lg["games"] if lg["games"] >= 5 else LEAGUE_AWAY_AVG

            # Elo + H2H ANTES do jogo (sem data leakage)
            elo_h, elo_a = elo_engine.get_before(h_name, a_name)
            elo_feats = {
                "elo_home": (elo_h - 1500.0) / 400.0,
                "elo_away": (elo_a - 1500.0) / 400.0,
                "elo_diff": (elo_h - elo_a)  / 400.0,
            }
            h2h_feats = h2h_index.get_features(h_name, a_name)

            features = build_full_features(
                h_all, h_home, a_all, a_away,
                h_id, a_id, h_pos, a_pos,
                lg_home, lg_away,
                elo_feats=elo_feats,
                h2h_feats=h2h_feats,
            )

            X_list.append(features)
            y_btts.append(1 if (hg > 0 and ag > 0) else 0)
            y_ou.append(1 if (hg + ag) > 2.5 else 0)

        # Atualizar TUDO após calcular features (sem data leakage)
        elo_engine.update(h_name, a_name, hg, ag)
        h2h_index.add(h_name, a_name, hg, ag)
        all_hist[h_id].append(match)
        all_hist[a_id].append(match)
        home_hist[h_id].append(match)
        away_hist[a_id].append(match)

        if hg > ag:
            points[key][h_id] += 3
        elif hg == ag:
            points[key][h_id] += 1
            points[key][a_id] += 1
        else:
            points[key][a_id] += 3

        league_goals[key]["home"]  += hg
        league_goals[key]["away"]  += ag
        league_goals[key]["games"] += 1

    X      = np.array(X_list, dtype=np.float32)
    y_btts = np.array(y_btts, dtype=np.int32)
    y_ou   = np.array(y_ou,   dtype=np.int32)

    print(f"Dataset mercados: {len(X)} amostras")
    print(f"  BTTS  — SIM : {y_btts.sum()}  NAO : {len(y_btts) - y_btts.sum()}")
    print(f"  O/U 2.5 — OVER: {(y_ou==1).sum()}  UNDER: {(y_ou==0).sum()}")
    return X, y_btts, y_ou


# ──────────────────────────────────────────────
# Treino
# ──────────────────────────────────────────────

def _train_binary(X_tr, y_tr, X_te, y_te, name, labels):
    weights = compute_sample_weight("balanced", y_tr)
    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_tr, y_tr, sample_weight=weights)

    acc    = (model.predict(X_te) == y_te).mean()
    y_pred = model.predict(X_te)
    print(f"\n{name}: {acc:.1%} accuracy no teste")
    print(classification_report(y_te, y_pred, target_names=labels, zero_division=0))
    return model


def train():
    print("=" * 52)
    print("  SharpBet — Treino BTTS + Over/Under 2.5")
    print("=" * 52 + "\n")

    X, y_btts, y_ou = build_market_dataset()

    # Dividir: 70% treino | 10% calibração | 20% teste
    idx = np.arange(len(X))
    tr_idx, temp_idx = train_test_split(idx, test_size=0.30, random_state=42)
    cal_idx, te_idx  = train_test_split(temp_idx, test_size=2/3, random_state=42)
    X_tr, X_cal, X_te = X[tr_idx], X[cal_idx], X[te_idx]

    # BTTS
    print("\n--- BTTS (Ambas Marcam) ---")
    btts_base = _train_binary(
        X_tr, y_btts[tr_idx], X_te, y_btts[te_idx],
        "BTTS", ["Nao (0)", "Sim (1)"],
    )
    print("A calibrar BTTS...")
    btts_model = CalibratedClassifierCV(btts_base, method="isotonic", cv=None)
    btts_model.fit(X_cal, y_btts[cal_idx])

    # Over/Under 2.5
    print("\n--- Over/Under 2.5 Golos ---")
    ou_base = _train_binary(
        X_tr, y_ou[tr_idx], X_te, y_ou[te_idx],
        "Over/Under 2.5", ["Under (0)", "Over (1)"],
    )
    print("A calibrar Over/Under...")
    ou_model = CalibratedClassifierCV(ou_base, method="isotonic", cv=None)
    ou_model.fit(X_cal, y_ou[cal_idx])

    # Guardar
    os.makedirs(os.path.dirname(BTTS_PATH), exist_ok=True)
    joblib.dump(btts_model, BTTS_PATH)
    joblib.dump(ou_model,   OU_PATH)
    print(f"\nModelos calibrados guardados:")
    print(f"  {BTTS_PATH}")
    print(f"  {OU_PATH}")

    btts_acc = round((btts_base.predict(X_te) == y_btts[te_idx]).mean() * 100, 1)
    ou_acc   = round((ou_base.predict(X_te)   == y_ou[te_idx]).mean()   * 100, 1)
    return btts_acc, ou_acc


if __name__ == "__main__":
    train()
