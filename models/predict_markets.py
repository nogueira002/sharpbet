"""
Previsão dos mercados secundários: BTTS e Over/Under 2.5.

predict_btts(features) → {"yes": 0.62, "no": 0.38}
predict_ou(features)   → {"over": 0.58, "under": 0.42}

features: vetor de 43 floats (35 base + 8 Elo/H2H)
Retorna None se o modelo ainda não estiver treinado.
"""

import os
import joblib

BTTS_PATH = os.path.join(os.path.dirname(__file__), "saved", "btts_model.pkl")
OU_PATH   = os.path.join(os.path.dirname(__file__), "saved", "ou_model.pkl")

_btts_model = None
_ou_model   = None


def _load_btts():
    global _btts_model
    if _btts_model is None:
        if not os.path.exists(BTTS_PATH):
            return None
        _btts_model = joblib.load(BTTS_PATH)
    return _btts_model


def _load_ou():
    global _ou_model
    if _ou_model is None:
        if not os.path.exists(OU_PATH):
            return None
        _ou_model = joblib.load(OU_PATH)
    return _ou_model


def predict_btts(features):
    """
    Retorna probabilidade de Ambas as Equipas Marcarem.

    Retorna: {"yes": 0.62, "no": 0.38} ou None se modelo indisponível.
    """
    model = _load_btts()
    if model is None:
        return None
    probs = model.predict_proba([features])[0]
    return {
        "no":  round(float(probs[0]), 4),
        "yes": round(float(probs[1]), 4),
    }


def predict_ou(features):
    """
    Retorna probabilidade de Over/Under 2.5 golos.

    Retorna: {"over": 0.58, "under": 0.42} ou None se modelo indisponível.
    """
    model = _load_ou()
    if model is None:
        return None
    probs = model.predict_proba([features])[0]
    return {
        "under": round(float(probs[0]), 4),
        "over":  round(float(probs[1]), 4),
    }
