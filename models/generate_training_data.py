"""
Gerador de dados sintéticos de treino.

Como não temos dados históricos reais (API com quota esgotada),
geramos 2000 jogos "inventados" com padrões realistas.

Conceito:
- Cada equipa tem uma "força" entre 0 e 1
- Equipas mais fortes ganham mais e marcam mais golos
- Adicionamos ruído para simular a imprevisibilidade do futebol

Quando tivermos dados reais da API, substituímos este ficheiro
e o modelo fica automaticamente mais preciso.
"""

import random
import csv
import os

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "saved", "training_data.csv")

# Features por ordem (igual ao build_match_features em features.py)
FEATURE_NAMES = [
    "home_win_rate", "home_draw_rate", "home_avg_scored", "home_avg_conceded",
    "home_clean_sheet_rate", "home_scored_2plus_rate",
    "away_win_rate", "away_draw_rate", "away_avg_scored", "away_avg_conceded",
    "away_clean_sheet_rate", "away_scored_2plus_rate",
    "result",  # 0=casa, 1=empate, 2=fora
]


def generate_team_stats(strength):
    """
    Dada a força de uma equipa (0-1), gera estatísticas realistas.

    Uma equipa forte tem mais vitórias, mais golos marcados, menos sofridos.
    Adicionamos ruído aleatório para simular imprevisibilidade.
    """
    noise = lambda: random.uniform(-0.1, 0.1)

    win_rate          = max(0, min(1, strength * 0.7 + noise()))
    draw_rate         = max(0, min(1 - win_rate, 0.25 + noise()))
    avg_scored        = max(0, 0.5 + strength * 2.5 + noise())
    avg_conceded      = max(0, 2.5 - strength * 2.0 + noise())
    clean_sheet_rate  = max(0, min(1, strength * 0.4 + noise()))
    scored_2plus_rate = max(0, min(1, strength * 0.6 + noise()))

    return [
        round(win_rate, 4),
        round(draw_rate, 4),
        round(avg_scored, 4),
        round(avg_conceded, 4),
        round(clean_sheet_rate, 4),
        round(scored_2plus_rate, 4),
    ]


def simulate_result(home_strength, away_strength):
    """
    Simula o resultado de um jogo com base nas forças das equipas.

    Calcula probabilidades base e sorteia o resultado com ruído.
    Retorna: 0 (casa), 1 (empate), 2 (fora)
    """
    # Vantagem de jogar em casa (~+10%)
    home_advantage = 0.1

    total = home_strength + away_strength + 0.3  # 0.3 = peso do empate
    p_home = (home_strength / total) + home_advantage
    p_draw = 0.3 / total
    p_away = (away_strength / total) - home_advantage

    # Normalizar para somar 1
    total_p = p_home + p_draw + p_away
    p_home /= total_p
    p_draw /= total_p
    p_away /= total_p

    # Adicionar ruído (futebol é imprevisível)
    r = random.random()
    if r < p_home:
        return 0  # Casa ganha
    elif r < p_home + p_draw:
        return 1  # Empate
    else:
        return 2  # Fora ganha


def generate(n_matches=2000, seed=42):
    random.seed(seed)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    rows = []
    for _ in range(n_matches):
        home_strength = random.uniform(0.1, 0.9)
        away_strength = random.uniform(0.1, 0.9)

        home_stats = generate_team_stats(home_strength)
        away_stats = generate_team_stats(away_strength)
        result     = simulate_result(home_strength, away_strength)

        rows.append(home_stats + away_stats + [result])

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FEATURE_NAMES)
        writer.writerows(rows)

    print(f"✅ {n_matches} jogos sintéticos gerados → {OUTPUT_PATH}")

    # Mostrar distribuição dos resultados
    results = [r[-1] for r in rows]
    print(f"   Casa: {results.count(0)}  Empate: {results.count(1)}  Fora: {results.count(2)}")


if __name__ == "__main__":
    generate()
