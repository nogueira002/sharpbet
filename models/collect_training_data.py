"""
Recolhe dados históricos reais da API-Football para treinar o modelo.

Versão 2: inclui venue-specific form e posição na liga calculada dos dados brutos.

Estratégia:
  - 1 request por liga/época → retorna todos os jogos terminados
  - Processa localmente: calcula forma, venue-form e standings para cada jogo
  - 24 requests → ~6000 jogos reais com 26 features cada

Uso:
  python -m models.collect_training_data          # usa raw_fixtures.json se existir
  python -m models.collect_training_data --force  # re-faz o fetch à API
"""

import os, json, csv, time, sys, requests
from collections import defaultdict
from config import HEADERS_APISPORTS, APISPORTS_BASE_URL
from models.features import build_match_features, FEATURE_NAMES, LEAGUE_HOME_AVG, LEAGUE_AWAY_AVG

RAW_PATH      = os.path.join(os.path.dirname(__file__), "saved", "raw_fixtures.json")
TRAINING_PATH = os.path.join(os.path.dirname(__file__), "saved", "training_data.csv")

LEAGUES_SEASONS = [
    # Big 5 europeus — 4 épocas cada
    (39,  2024, "Premier League"),
    (39,  2023, "Premier League"),
    (39,  2022, "Premier League"),
    (39,  2021, "Premier League"),
    (140, 2024, "La Liga"),
    (140, 2023, "La Liga"),
    (140, 2022, "La Liga"),
    (140, 2021, "La Liga"),
    (78,  2024, "Bundesliga"),
    (78,  2023, "Bundesliga"),
    (78,  2022, "Bundesliga"),
    (78,  2021, "Bundesliga"),
    (135, 2024, "Serie A"),
    (135, 2023, "Serie A"),
    (135, 2022, "Serie A"),
    (135, 2021, "Serie A"),
    (61,  2024, "Ligue 1"),
    (61,  2023, "Ligue 1"),
    (61,  2022, "Ligue 1"),
    (61,  2021, "Ligue 1"),
    # Portugal
    (94,  2024, "Liga Portugal"),
    (94,  2023, "Liga Portugal"),
    (94,  2022, "Liga Portugal"),
    (94,  2021, "Liga Portugal"),
    # Europa competições UEFA
    (2,   2024, "Champions League"),
    (2,   2023, "Champions League"),
    (2,   2022, "Champions League"),
    (3,   2024, "Europa League"),
    (3,   2023, "Europa League"),
    (3,   2022, "Europa League"),
    # Outras ligas relevantes
    (88,  2024, "Eredivisie"),
    (88,  2023, "Eredivisie"),
    (203, 2024, "Super Lig"),
    (203, 2023, "Super Lig"),
    (71,  2024, "Brasileirao"),
    (71,  2023, "Brasileirao"),
    (128, 2024, "Liga Profesional"),
    (128, 2023, "Liga Profesional"),
    # Conference League (equipas de muitas ligas europeias)
    (848, 2024, "Conference League"),
    (848, 2023, "Conference League"),
    (848, 2022, "Conference League"),
    # Ligas domésticas das equipas frequentes na Europa
    (40,  2024, "Scottish Premiership"),   # Celtic, Rangers
    (40,  2023, "Scottish Premiership"),
    (144, 2024, "Belgian Pro League"),     # Club Brugge, Anderlecht
    (144, 2023, "Belgian Pro League"),
    (106, 2024, "Ekstraklasa"),            # Legia, Jagiellonia
    (106, 2023, "Ekstraklasa"),
    (345, 2024, "Czech Fortuna Liga"),     # Plzen, Slavia, Sparta
    (345, 2023, "Czech Fortuna Liga"),
    (197, 2024, "Greek Super League"),     # PAOK, Panathinaikos
    (197, 2023, "Greek Super League"),
    (218, 2024, "Austrian Bundesliga"),    # Salzburg, Sturm Graz
    (218, 2023, "Austrian Bundesliga"),
    (286, 2024, "Serbian SuperLiga"),      # Red Star, Partizan
    (286, 2023, "Serbian SuperLiga"),
    (271, 2024, "Hungarian NB I"),         # Ferencvaros
    (271, 2023, "Hungarian NB I"),
    (210, 2024, "Croatian HNL"),           # Dinamo Zagreb, HNK Rijeka
    (210, 2023, "Croatian HNL"),
    (119, 2024, "Danish Superliga"),       # Copenhagen, Midtjylland
    (119, 2023, "Danish Superliga"),
]

MIN_FORM_GAMES = 3  # Mínimo de jogos históricos para incluir amostra


# ──────────────────────────────────────────────
# 1. FETCH
# ──────────────────────────────────────────────

def fetch_league_season(league_id, season, name):
    url = f"{APISPORTS_BASE_URL}/fixtures"
    params = {"league": league_id, "season": season, "status": "FT"}
    print(f"  Fetch: {name} {season}...", end=" ", flush=True)
    try:
        r = requests.get(url, headers=HEADERS_APISPORTS, params=params, timeout=20)
        r.raise_for_status()
        matches = r.json().get("response", [])
        print(f"{len(matches)} jogos")
        return matches
    except Exception as e:
        print(f"ERRO: {e}")
        return []


def fetch_all_raw(force=False):
    if not force and os.path.exists(RAW_PATH):
        print(f"[OK] raw_fixtures.json ja existe — a reutilizar (--force para re-fetch)\n")
        with open(RAW_PATH) as f:
            return json.load(f)

    print(f"A recolher {len(LEAGUES_SEASONS)} ligas/epocas...\n")
    all_matches = []
    for i, (lid, season, name) in enumerate(LEAGUES_SEASONS):
        all_matches.extend(fetch_league_season(lid, season, name))
        if i < len(LEAGUES_SEASONS) - 1:
            time.sleep(6)  # respeitar rate limit: 10 req/min

    os.makedirs(os.path.dirname(RAW_PATH), exist_ok=True)
    with open(RAW_PATH, "w") as f:
        json.dump(all_matches, f)
    print(f"\n[OK] {len(all_matches)} jogos guardados\n")
    return all_matches


# ──────────────────────────────────────────────
# 2. PARSE
# ──────────────────────────────────────────────

def parse_match(raw):
    hg = raw["goals"]["home"] or 0
    ag = raw["goals"]["away"] or 0
    return {
        "date":      raw["fixture"]["date"],
        "league_id": raw["league"]["id"],
        "season":    raw["league"]["season"],
        "home_id":   raw["teams"]["home"]["id"],
        "away_id":   raw["teams"]["away"]["id"],
        "home_goals": hg,
        "away_goals": ag,
        "winner": True if hg > ag else (False if ag > hg else None),
    }


# ──────────────────────────────────────────────
# 3. BUILD DATASET
# ──────────────────────────────────────────────

def build_dataset(raw_matches):
    """
    Para cada jogo histórico calcula:
      - Forma recente dos últimas 10 jogos (todos)
      - Forma venue-específica: últimos 5 em casa / fora
      - Posição na liga no momento do jogo
    """
    matches = [parse_match(m) for m in raw_matches]
    matches.sort(key=lambda m: m["date"])

    # Histórico por equipa
    all_hist   = defaultdict(list)   # todos os jogos
    home_hist  = defaultdict(list)   # só jogos em casa
    away_hist  = defaultdict(list)   # só jogos fora

    # Standings: points[league_key][team_id] = pontos acumulados
    points     = defaultdict(lambda: defaultdict(int))

    # Médias de golos por liga/época (para Poisson)
    # Atualizado APÓS cada jogo para evitar data leakage
    league_goals = defaultdict(lambda: {"home": 0, "away": 0, "games": 0})

    # Total de equipas por liga/época (para normalizar posição)
    teams_set  = defaultdict(set)
    for m in matches:
        key = (m["league_id"], m["season"])
        teams_set[key].add(m["home_id"])
        teams_set[key].add(m["away_id"])
    num_teams = {k: len(v) for k, v in teams_set.items()}

    rows    = []
    skipped = 0

    for match in matches:
        h_id  = match["home_id"]
        a_id  = match["away_id"]
        key   = (match["league_id"], match["season"])
        total = num_teams.get(key, 20)

        # Forma recente ANTES deste jogo
        h_all  = all_hist[h_id][-10:]
        a_all  = all_hist[a_id][-10:]
        h_home = home_hist[h_id][-5:]    # últimos 5 jogos em casa
        a_away = away_hist[a_id][-5:]    # últimos 5 jogos fora

        if len(h_all) < MIN_FORM_GAMES or len(a_all) < MIN_FORM_GAMES:
            skipped += 1
        else:
            # Posição na liga (normalizada)
            pts_sorted = sorted(points[key].values(), reverse=True)
            def get_pos_norm(team_id):
                pts = points[key].get(team_id, 0)
                rank = next((i for i, p in enumerate(pts_sorted) if p <= pts), len(pts_sorted))
                return rank / max(total - 1, 1)

            h_pos = get_pos_norm(h_id)
            a_pos = get_pos_norm(a_id)

            # Médias da liga ATÉ AGORA (sem este jogo)
            lg = league_goals[key]
            lg_home = lg["home"] / lg["games"] if lg["games"] >= 5 else LEAGUE_HOME_AVG
            lg_away = lg["away"] / lg["games"] if lg["games"] >= 5 else LEAGUE_AWAY_AVG

            features = build_match_features(
                h_all, h_home, a_all, a_away,
                h_id, a_id, h_pos, a_pos,
                lg_home, lg_away,
            )
            hg, ag  = match["home_goals"], match["away_goals"]
            result  = 0 if hg > ag else (1 if hg == ag else 2)
            rows.append(features + [result])

        # Atualizar histórico, standings e médias DEPOIS de calcular features
        all_hist[h_id].append(match)
        all_hist[a_id].append(match)
        home_hist[h_id].append(match)
        away_hist[a_id].append(match)

        hg, ag = match["home_goals"], match["away_goals"]
        if hg > ag:
            points[key][h_id] += 3
        elif hg == ag:
            points[key][h_id] += 1
            points[key][a_id] += 1
        else:
            points[key][a_id] += 3

        # Atualizar médias de golos da liga
        league_goals[key]["home"]  += hg
        league_goals[key]["away"]  += ag
        league_goals[key]["games"] += 1

    results = [r[-1] for r in rows]
    print(f"  Jogos total       : {len(matches)}")
    print(f"  Amostras validas  : {len(rows)}  (sem historico suficiente: {skipped})")
    print(f"  Casa: {results.count(0)}  Empate: {results.count(1)}  Fora: {results.count(2)}")
    return rows


# ──────────────────────────────────────────────
# 4. GUARDAR CSV
# ──────────────────────────────────────────────

def save_csv(rows):
    os.makedirs(os.path.dirname(TRAINING_PATH), exist_ok=True)
    with open(TRAINING_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FEATURE_NAMES)
        writer.writerows(rows)
    print(f"\n[OK] {len(rows)} amostras em training_data.csv ({len(FEATURE_NAMES)-1} features)")
    print(f"     Proximo passo: python -m models.train")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    force = "--force" in sys.argv
    print("=" * 50)
    print("  SharpBet — Recolha de dados de treino v2")
    print("=" * 50 + "\n")
    raw  = fetch_all_raw(force=force)
    print(f"A processar {len(raw)} jogos...\n")
    rows = build_dataset(raw)
    save_csv(rows)
