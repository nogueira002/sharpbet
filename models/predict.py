"""
Previsão com ensemble XGBoost + LSTM.

XGBoost (60%) — aprende de stats agregadas: win_rate, xG, posição...
LSTM    (40%) — aprende de sequências: a ordem dos resultados importa

Combinação: final = 0.6 × XGBoost + 0.4 × LSTM

Se o LSTM ainda não estiver treinado, usa apenas XGBoost.
"""

import os
import numpy as np
import joblib

from models.features import build_full_features, LEAGUE_HOME_AVG, LEAGUE_AWAY_AVG
from models.lstm_data import build_sequence

XGB_PATH  = os.path.join(os.path.dirname(__file__), "saved", "xgboost_model.pkl")
LSTM_PATH = os.path.join(os.path.dirname(__file__), "saved", "lstm_model.keras")

_xgb_model  = None
_lstm_model = None


def _load_xgb():
    global _xgb_model
    if _xgb_model is None:
        if not os.path.exists(XGB_PATH):
            raise FileNotFoundError("XGBoost nao treinado. Corre: python -m models.train")
        _xgb_model = joblib.load(XGB_PATH)
    return _xgb_model


def _load_lstm():
    global _lstm_model
    if _lstm_model is None:
        if not os.path.exists(LSTM_PATH):
            return None
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
        from tensorflow import keras
        _lstm_model = keras.models.load_model(LSTM_PATH)
    return _lstm_model


def _xgb_probs(features):
    probs = _load_xgb().predict_proba([features])[0]
    return {"home": float(probs[0]), "draw": float(probs[1]), "away": float(probs[2])}


def _lstm_probs(home_form, away_form, home_team_id, away_team_id):
    model = _load_lstm()
    if model is None:
        return None
    h_seq = np.array([build_sequence(home_form, home_team_id)], dtype=np.float32)
    a_seq = np.array([build_sequence(away_form, away_team_id)], dtype=np.float32)
    probs = model.predict([h_seq, a_seq], verbose=0)[0]
    return {"home": float(probs[0]), "draw": float(probs[1]), "away": float(probs[2])}


def predict_match(
    home_form_all, home_form_home,
    away_form_all, away_form_away,
    home_team_id=None, away_team_id=None,
    home_position_norm=0.5, away_position_norm=0.5,
    league_home_avg=LEAGUE_HOME_AVG, league_away_avg=LEAGUE_AWAY_AVG,
    elo_feats=None, h2h_feats=None,
):
    """
    Previsão ensemble XGBoost + LSTM.

    elo_feats : {"elo_home": float, "elo_away": float, "elo_diff": float}
    h2h_feats : {"h2h_home_wins": float, ...}

    Retorna: {"home": 0.45, "draw": 0.28, "away": 0.27}
    """
    # XGBoost features (43 números: 35 base + 8 Elo/H2H)
    features = build_full_features(
        home_form_all, home_form_home,
        away_form_all, away_form_away,
        home_team_id,  away_team_id,
        home_position_norm, away_position_norm,
        league_home_avg, league_away_avg,
        elo_feats=elo_feats, h2h_feats=h2h_feats,
    )
    xgb = _xgb_probs(features)

    # LSTM (se disponível)
    lstm = _lstm_probs(home_form_all, away_form_all, home_team_id, away_team_id)

    if lstm is not None:
        # Ensemble: XGBoost 60% + LSTM 40%
        final = {
            "home": round(0.6 * xgb["home"] + 0.4 * lstm["home"], 4),
            "draw": round(0.6 * xgb["draw"] + 0.4 * lstm["draw"], 4),
            "away": round(0.6 * xgb["away"] + 0.4 * lstm["away"], 4),
        }
        source = "XGBoost+LSTM"
    else:
        # Fallback só XGBoost (antes do LSTM ser treinado)
        final = {k: round(v, 4) for k, v in xgb.items()}
        source = "XGBoost"

    final["_source"] = source
    return final
