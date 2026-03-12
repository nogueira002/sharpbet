"""
Preparação de dados sequenciais para o LSTM.

O XGBoost recebe features agregadas (win_rate, xG, etc.)
O LSTM recebe a SEQUÊNCIA de jogos — a ordem importa!

Cada jogo na sequência = 5 números:
  [golos_marcados/5, golos_sofridos/5, ganhou, empatou, perdeu]

Exemplo para uma equipa:
  Jogo 1: [0.4, 0.2, 1, 0, 0]  → marcou 2, sofreu 1, ganhou
  Jogo 2: [0.0, 0.4, 0, 0, 1]  → marcou 0, sofreu 2, perdeu
  Jogo 3: [0.6, 0.0, 1, 0, 0]  → marcou 3, sofreu 0, ganhou
  ...
"""

import os
import json
import numpy as np
from collections import defaultdict

RAW_PATH = os.path.join(os.path.dirname(__file__), "saved", "raw_fixtures.json")
SEQ_PATH = os.path.join(os.path.dirname(__file__), "saved", "lstm_sequences.npz")

SEQ_LEN  = 10  # últimos N jogos por equipa
N_FEATS  = 5   # features por jogo na sequência
MIN_FORM = 3   # mínimo de jogos históricos para incluir amostra


def match_to_vector(match, team_id):
    """
    Converte um jogo num vetor de 5 números do ponto de vista do team_id.
    Normalizado para que todos os valores estejam entre 0 e 1.
    """
    is_home  = match["home_id"] == team_id
    scored   = match["home_goals"] if is_home else match["away_goals"]
    conceded = match["away_goals"] if is_home else match["home_goals"]
    w        = match["winner"]
    won      = (w is True and is_home) or (w is False and not is_home)
    drew     = w is None
    lost     = not won and not drew

    return [
        min(scored,   5) / 5,  # golos marcados (0-1)
        min(conceded, 5) / 5,  # golos sofridos (0-1)
        float(won),            # 1 se ganhou, 0 se não
        float(drew),           # 1 se empatou, 0 se não
        float(lost),           # 1 se perdeu, 0 se não
    ]


def build_sequence(form, team_id):
    """
    Converte lista de jogos numa sequência de shape (SEQ_LEN, N_FEATS).
    Se a equipa tem menos de SEQ_LEN jogos → preenche com zeros no início
    (zeros = "sem informação" → o modelo aprende a ignorá-los).
    """
    vectors = [match_to_vector(m, team_id) for m in form[-SEQ_LEN:]]
    # Padding: preenche início com zeros se tiver poucos jogos
    pad = SEQ_LEN - len(vectors)
    return [[0.0] * N_FEATS] * pad + vectors


def build_dataset():
    """
    Constrói o dataset de sequências a partir do raw_fixtures.json.

    Retorna:
      X_home : (n, SEQ_LEN, N_FEATS) — sequências da equipa da casa
      X_away : (n, SEQ_LEN, N_FEATS) — sequências da equipa de fora
      y      : (n,)                  — resultado: 0=casa, 1=empate, 2=fora
    """
    if not os.path.exists(RAW_PATH):
        raise FileNotFoundError("raw_fixtures.json nao encontrado. Corre collect_training_data primeiro.")

    with open(RAW_PATH) as f:
        raw = json.load(f)

    # Parse e ordenar por data
    matches = []
    for m in raw:
        hg = m["goals"]["home"] or 0
        ag = m["goals"]["away"] or 0
        matches.append({
            "date":       m["fixture"]["date"],
            "home_id":    m["teams"]["home"]["id"],
            "away_id":    m["teams"]["away"]["id"],
            "home_goals": hg,
            "away_goals": ag,
            "winner": True if hg > ag else (False if ag > hg else None),
        })
    matches.sort(key=lambda m: m["date"])

    team_hist = defaultdict(list)
    X_home_list, X_away_list, y_list = [], [], []

    for match in matches:
        h_id   = match["home_id"]
        a_id   = match["away_id"]
        h_form = team_hist[h_id]
        a_form = team_hist[a_id]

        if len(h_form) >= MIN_FORM and len(a_form) >= MIN_FORM:
            X_home_list.append(build_sequence(h_form, h_id))
            X_away_list.append(build_sequence(a_form, a_id))
            hg, ag = match["home_goals"], match["away_goals"]
            y_list.append(0 if hg > ag else (1 if hg == ag else 2))

        # Adicionar APÓS calcular (evita data leakage)
        team_hist[h_id].append(match)
        team_hist[a_id].append(match)

    X_home = np.array(X_home_list, dtype=np.float32)
    X_away = np.array(X_away_list, dtype=np.float32)
    y      = np.array(y_list,      dtype=np.int32)

    unique, counts = np.unique(y, return_counts=True)
    print(f"Dataset LSTM: {len(y)} amostras")
    print(f"  Shape sequencias: {X_home.shape}")
    print(f"  Casa: {counts[0]}  Empate: {counts[1]}  Fora: {counts[2]}")
    return X_home, X_away, y


def save_sequences():
    X_home, X_away, y = build_dataset()
    os.makedirs(os.path.dirname(SEQ_PATH), exist_ok=True)
    np.savez(SEQ_PATH, X_home=X_home, X_away=X_away, y=y)
    print(f"Sequencias guardadas: {SEQ_PATH}")
    return X_home, X_away, y


def load_sequences(force=False):
    if not force and os.path.exists(SEQ_PATH):
        data = np.load(SEQ_PATH)
        print(f"Sequencias carregadas: {data['X_home'].shape[0]} amostras")
        return data["X_home"], data["X_away"], data["y"]
    return save_sequences()


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    if force or not os.path.exists(SEQ_PATH):
        save_sequences()
    else:
        # Regenera sempre quando corrido directamente
        save_sequences()
