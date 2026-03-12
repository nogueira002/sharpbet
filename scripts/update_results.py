"""
Vai buscar os resultados de ontem e atualiza a base de dados.

Uso:
  python -m scripts.update_results          # resultados de ontem
  python -m scripts.update_results --date 2026-03-01   # data específica

Corre todos os dias depois do main.py (ou logo de manhã antes de correr hoje).
"""

import sys
import re
import json
import os
import unicodedata
import difflib
from datetime import date, timedelta
from config import fd_api_get, SUPPORTED_COMPETITIONS
from models.database import init_db, update_result, get_performance_summary

RAW_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "saved", "raw_fixtures.json")


def _norm(name):
    nfkd = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in nfkd if not unicodedata.combining(c))
    name = re.sub(r"[^\w\s]", " ", name.lower())
    name = re.sub(r"\b(fc|afc|sc|cf|rc|ss)\b", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _similarity(a, b):
    na, nb = _norm(a), _norm(b)
    if na == nb or na in nb or nb in na:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def fetch_results(target_date: str):
    """
    Vai buscar todos os jogos terminados numa data específica.
    Retorna lista de {fixture_id, home_team, away_team, home_goals, away_goals, result}
    """
    try:
        r    = fd_api_get("/matches", {"date": target_date})
        data = r.json()
    except Exception as e:
        print(f"Erro ao buscar resultados: {e}")
        return []

    results = []
    for match in data.get("matches", []):
        if match.get("status") != "FINISHED":
            continue
        code = match.get("competition", {}).get("code", "")
        if code not in SUPPORTED_COMPETITIONS:
            continue

        score = match.get("score", {}).get("fullTime", {})
        hg    = score.get("home")
        ag    = score.get("away")
        if hg is None or ag is None:
            continue

        results.append({
            "fixture_id":   match["id"],
            "home_team":    match["homeTeam"]["name"],
            "home_team_id": match["homeTeam"]["id"],
            "away_team":    match["awayTeam"]["name"],
            "away_team_id": match["awayTeam"]["id"],
            "home_goals":   hg,
            "away_goals":   ag,
            "result":       "H" if hg > ag else ("D" if hg == ag else "A"),
            "date":         match.get("utcDate", ""),
            "league_code":  code,
            "season":       match.get("season", {}).get("startYear", date.today().year),
        })

    return results


def append_to_training_data(results):
    """
    Converte os resultados para o formato raw_fixtures.json e guarda.
    Permite retreinar o modelo com dados mais recentes.
    """
    if not os.path.exists(RAW_PATH):
        return 0

    with open(RAW_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    existing_ids = {m["fixture"]["id"] for m in raw}
    added = 0

    for r in results:
        if r["fixture_id"] in existing_ids:
            continue
        raw.append({
            "fixture": {"id": r["fixture_id"], "date": r["date"]},
            "league":  {"id": r["league_code"], "name": r["league_code"], "season": r["season"]},
            "teams": {
                "home": {"id": r["home_team_id"], "name": r["home_team"]},
                "away": {"id": r["away_team_id"], "name": r["away_team"]},
            },
            "goals": {"home": r["home_goals"], "away": r["away_goals"]},
        })
        existing_ids.add(r["fixture_id"])
        added += 1

    if added > 0:
        with open(RAW_PATH, "w", encoding="utf-8") as f:
            json.dump(raw, f)

    return added


def run(target_date: str = None):
    if target_date is None:
        target_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"A buscar resultados de {target_date}...")
    init_db()

    results = fetch_results(target_date)
    if not results:
        print("  Nenhum jogo terminado encontrado.")
        return

    print(f"  {len(results)} jogos terminados encontrados.\n")

    updated = 0
    for r in results:
        update_result(r["fixture_id"], r["result"])
        print(f"  {r['home_team']} {r['home_goals']}-{r['away_goals']} {r['away_team']}  [{r['result']}]")
        updated += 1

    print(f"\n  {updated} resultados guardados na BD.")

    # Guardar jogos para treino futuro
    added = append_to_training_data(results)
    if added > 0:
        print(f"  {added} jogos novos adicionados ao raw_fixtures.json (para retreino).")

    # Mostrar ROI acumulado
    stats = get_performance_summary()
    if stats:
        print(f"\n{'='*50}")
        print(f"  PERFORMANCE ACUMULADA")
        print(f"{'='*50}")
        print(f"  Tips totais  : {stats['total_tips']}")
        print(f"  Win rate     : {stats['win_rate']}%")
        print(f"  ROI          : {stats['roi']:+.1f}%")
        print(f"  Lucro neto   : {stats['net_profit']:+.2f}% da banca")
        print(f"{'='*50}\n")
    else:
        print("\n  (Ainda sem resultados suficientes para calcular ROI)")


if __name__ == "__main__":
    # Aceita --date YYYY-MM-DD opcional
    target = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--date" and i + 1 < len(sys.argv) - 1:
            target = sys.argv[i + 2]
        elif re.match(r"\d{4}-\d{2}-\d{2}", arg):
            target = arg

    run(target)
