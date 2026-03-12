"""
Reconstrói training_data.csv com Elo + H2H features.

Lê raw_fixtures.json (já existente, sem chamadas à API).
Processa cada jogo cronologicamente:
  - Forma recente (últimos 10 jogos)
  - Standings na liga
  - Elo ratings ANTES do jogo (sem data leakage)
  - H2H stats ANTES do jogo

Output: training_data.csv com 43 features (+1 result = 44 colunas)

Uso:
  python -m models.rebuild_features
"""

import os
import json
import csv
from collections import defaultdict

from models.features import (
    build_full_features, FULL_FEATURE_NAMES,
    LEAGUE_HOME_AVG, LEAGUE_AWAY_AVG,
)
from models.elo import EloEngine, ELO_PATH
from models.h2h import H2HIndex

RAW_PATH      = os.path.join(os.path.dirname(__file__), "saved", "raw_fixtures.json")
TRAINING_PATH = os.path.join(os.path.dirname(__file__), "saved", "training_data.csv")
MIN_FORM      = 3


def rebuild():
    print("=" * 54)
    print("  SharpBet — Rebuild Training Data v4 (43 features)")
    print("=" * 54 + "\n")

    if not os.path.exists(RAW_PATH):
        print("ERRO: raw_fixtures.json nao encontrado.")
        print("Corre: python -m models.collect_training_data")
        return

    print("A carregar raw_fixtures.json...")
    with open(RAW_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    print(f"  {len(raw)} jogos brutos carregados\n")

    # Parse + ordenar por data
    matches = []
    for m in raw:
        hg = m["goals"]["home"] or 0
        ag = m["goals"]["away"] or 0
        matches.append({
            "fixture_id": m["fixture"]["id"],
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
    print(f"A processar {len(matches)} jogos com Elo + H2H...\n")

    # Estado progressivo (atualizado APÓS calcular features — sem data leakage)
    elo_engine = EloEngine()
    h2h_index  = H2HIndex()
    all_hist   = defaultdict(list)   # team_id -> todos os jogos
    home_hist  = defaultdict(list)   # team_id -> só jogos em casa
    away_hist  = defaultdict(list)   # team_id -> só jogos fora
    points     = defaultdict(lambda: defaultdict(int))
    league_goals = defaultdict(lambda: {"home": 0, "away": 0, "games": 0})

    # Número de equipas por liga/época (para normalizar posição)
    teams_set = defaultdict(set)
    for m in matches:
        key = (m["league_id"], m["season"])
        teams_set[key].add(m["home_id"])
        teams_set[key].add(m["away_id"])
    num_teams = {k: len(v) for k, v in teams_set.items()}

    rows    = []
    skipped = 0

    for match in matches:
        h_id    = match["home_id"]
        a_id    = match["away_id"]
        h_name  = match["home_name"]
        a_name  = match["away_name"]
        hg      = match["home_goals"]
        ag      = match["away_goals"]
        key     = (match["league_id"], match["season"])
        total   = num_teams.get(key, 20)

        # Forma ANTES deste jogo
        h_form_all  = list(all_hist[h_id][-10:])
        a_form_all  = list(all_hist[a_id][-10:])
        h_form_home = list(home_hist[h_id][-5:])
        a_form_away = list(away_hist[a_id][-5:])

        # Posição na liga ANTES deste jogo
        pts_sorted = sorted(points[key].values(), reverse=True)
        def pos_norm(team_id):
            pts  = points[key].get(team_id, 0)
            rank = next((i for i, p in enumerate(pts_sorted) if p <= pts), len(pts_sorted))
            return rank / max(total - 1, 1)
        h_pos = pos_norm(h_id)
        a_pos = pos_norm(a_id)

        # Médias da liga ANTES deste jogo
        lg = league_goals[key]
        lg_home = lg["home"] / lg["games"] if lg["games"] >= 5 else LEAGUE_HOME_AVG
        lg_away = lg["away"] / lg["games"] if lg["games"] >= 5 else LEAGUE_AWAY_AVG

        if len(h_form_all) >= MIN_FORM and len(a_form_all) >= MIN_FORM:
            # Elo ANTES (sem atualizar ainda)
            elo_h, elo_a = elo_engine.get_before(h_name, a_name)
            elo_feats = {
                "elo_home": (elo_h - 1500.0) / 400.0,
                "elo_away": (elo_a - 1500.0) / 400.0,
                "elo_diff": (elo_h - elo_a)  / 400.0,
            }

            # H2H ANTES (sem adicionar ainda)
            h2h_feats = h2h_index.get_features(h_name, a_name)

            features = build_full_features(
                h_form_all, h_form_home,
                a_form_all, a_form_away,
                h_id, a_id, h_pos, a_pos,
                lg_home, lg_away,
                elo_feats=elo_feats,
                h2h_feats=h2h_feats,
            )
            result = 0 if hg > ag else (1 if hg == ag else 2)
            rows.append(features + [result])
        else:
            skipped += 1

        # Atualizar TUDO após calcular features
        elo_engine.update(h_name, a_name, hg, ag)
        h2h_index.add(h_name, a_name, hg, ag)
        all_hist[h_id].append(match)
        all_hist[a_id].append(match)
        home_hist[h_id].append(match)
        away_hist[a_id].append(match)

        if   hg > ag: points[key][h_id] += 3
        elif hg == ag:
            points[key][h_id] += 1
            points[key][a_id] += 1
        else:         points[key][a_id] += 3

        league_goals[key]["home"]  += hg
        league_goals[key]["away"]  += ag
        league_goals[key]["games"] += 1

    # Guardar Elo atualizado
    elo_engine.save(ELO_PATH)

    # Estatísticas
    results = [r[-1] for r in rows]
    print(f"  Jogos processados : {len(matches)}")
    print(f"  Amostras validas  : {len(rows)}  (skipped: {skipped})")
    print(f"  Casa: {results.count(0)}  Empate: {results.count(1)}  Fora: {results.count(2)}")
    print(f"  Features por jogo : {len(rows[0]) - 1}")

    # Guardar CSV
    os.makedirs(os.path.dirname(TRAINING_PATH), exist_ok=True)
    with open(TRAINING_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FULL_FEATURE_NAMES)
        writer.writerows(rows)

    print(f"\n[OK] training_data.csv guardado com {len(rows)} amostras x {len(rows[0])-1} features")
    print(f"[OK] Elo ratings guardados para {len(elo_engine._ratings)} equipas")
    print(f"\nProximo passo:")
    print(f"  python -m models.train")
    print(f"  python -m models.train_markets")


if __name__ == "__main__":
    rebuild()
