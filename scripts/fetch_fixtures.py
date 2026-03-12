from datetime import datetime
from config import USE_MOCK, fd_api_get, SUPPORTED_COMPETITIONS


def fetch_todays_fixtures(target_date=None):
    """
    Vai buscar todos os jogos de uma data das ligas suportadas.
    Se target_date for None, usa hoje.
    """
    if USE_MOCK:
        from scripts.mock_data import MOCK_FIXTURES
        return MOCK_FIXTURES

    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    today = target_date
    try:
        r    = fd_api_get("/matches", {"date": today})
        data = r.json()

        fixtures = []
        for match in data.get("matches", []):
            code = match.get("competition", {}).get("code", "")
            if code not in SUPPORTED_COMPETITIONS:
                continue
            # TIMED = hora confirmada, SCHEDULED = sem hora ainda
            if match.get("status") not in ("SCHEDULED", "TIMED"):
                continue

            home = match.get("homeTeam", {})
            away = match.get("awayTeam", {})
            # Jogos de playoff cujos participantes ainda não são conhecidos têm id=None
            if not home.get("id") or not away.get("id"):
                continue

            comp = SUPPORTED_COMPETITIONS[code]
            fixtures.append({
                "fixture_id":   match["id"],
                "league_id":    code,
                "season":       match.get("season", {}).get("startYear", datetime.now().year),
                "league":       comp["name"],
                "country":      comp["country"],
                "date":         match["utcDate"][:16].replace("T", " "),
                "home_team":    home.get("name", ""),
                "home_team_id": home["id"],
                "away_team":    away.get("name", ""),
                "away_team_id": away["id"],
                "status":       "upcoming",
            })

        print(f"[fd.org] {len(fixtures)} jogos hoje nas ligas suportadas")
        return fixtures

    except Exception as e:
        print(f"Erro ao recolher fixtures: {e}")
        return []


def fetch_team_recent_form(team_id, last_n=10):
    """
    Vai buscar os últimos N jogos terminados de uma equipa.
    Retorna lista ordenada do mais antigo para o mais recente
    (analyze.py usa [-3:] e [-5:] para o momentum mais recente).
    """
    if USE_MOCK:
        from scripts.mock_data import MOCK_FORM
        return MOCK_FORM.get(team_id, [])

    try:
        r = fd_api_get(f"/teams/{team_id}/matches", {
            "status": "FINISHED",
            "limit":  last_n,
        })

        matches_raw = r.json().get("matches", [])
        # Garantir ordem: mais antigo primeiro (mais recente no fim)
        matches_sorted = sorted(matches_raw, key=lambda m: m.get("utcDate", ""))

        form = []
        for match in matches_sorted:
            score = match.get("score", {}).get("fullTime", {})
            hg    = score.get("home") or 0
            ag    = score.get("away") or 0
            form.append({
                "home_id":    match["homeTeam"]["id"],
                "away_id":    match["awayTeam"]["id"],
                "home_goals": hg,
                "away_goals": ag,
                "winner": True if hg > ag else (False if ag > hg else None),
            })
        return form

    except Exception as e:
        print(f"Sem forma para equipa {team_id}: {e}")
        return []


def fetch_standings(competition_code, season=None):
    """
    Vai buscar a tabela classificativa atual de uma liga.
    Retorna dict: {team_id: position_norm} onde 0=1º, 1=último.
    1 request por liga — é feito cache em analyze.py.
    """
    if USE_MOCK:
        return {}

    try:
        r    = fd_api_get(f"/competitions/{competition_code}/standings")
        data = r.json()

        standings_list = data.get("standings", [])
        if not standings_list:
            return {}

        # Usar TOTAL (não HOME/AWAY separados)
        table = next(
            (s["table"] for s in standings_list if s.get("type") == "TOTAL"),
            standings_list[0]["table"],
        )

        total = len(table)
        return {
            entry["team"]["id"]: (entry["position"] - 1) / max(total - 1, 1)
            for entry in table
        }

    except Exception as e:
        print(f"Sem standings para {competition_code}: {e}")
        return {}


def fetch_injuries(fixture_id):
    """Lesões não estão disponíveis no plano gratuito do football-data.org."""
    return {}
