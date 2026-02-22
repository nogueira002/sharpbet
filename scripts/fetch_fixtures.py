import requests
from datetime import datetime
from config import HEADERS_FOOTBALL, RAPIDAPI_HOST_FOOTBALL

def fetch_todays_fixtures():
    """
    Vai buscar todos os jogos de hoje à API.
    Retorna APENAS jogos que ainda não começaram (upcoming).
    """
    today = datetime.now().strftime("%Y%m%d")
    url = f"https://{RAPIDAPI_HOST_FOOTBALL}/football-get-matches-by-date"
    params = {"date": today}

    try:
        response = requests.get(url, headers=HEADERS_FOOTBALL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        all_matches = data.get("response", {}).get("matches", [])

        fixtures = []
        for match in all_matches:
            status = match.get("status", {})

            # Ignora jogos já terminados, cancelados ou adiados
            if status.get("finished") or status.get("cancelled"):
                continue

            fixture = {
                "fixture_id": match["id"],
                "league_id": match.get("leagueId"),
                "date": match.get("time"),
                "home_team": match["home"]["name"],
                "home_team_id": match["home"]["id"],
                "away_team": match["away"]["name"],
                "away_team_id": match["away"]["id"],
                "status": "upcoming",
            }
            fixtures.append(fixture)

        print(f"📅 {len(all_matches)} jogos totais hoje → {len(fixtures)} ainda por jogar")
        return fixtures

    except Exception as e:
        print(f"❌ Erro ao recolher fixtures: {e}")
        return []


def fetch_team_recent_form(team_id, last_n=5):
    """
    Vai buscar os últimos N jogos de uma equipa.
    """
    url = f"https://{RAPIDAPI_HOST_FOOTBALL}/football-get-matches-by-team"
    params = {"teamId": team_id, "last": last_n}

    try:
        response = requests.get(url, headers=HEADERS_FOOTBALL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        form = []
        matches = data.get("response", {}).get("matches", [])

        for match in matches:
            status = match.get("status", {})
            if not status.get("finished"):
                continue

            result = {
                "home_id": match["home"]["id"],
                "away_id": match["away"]["id"],
                "home_goals": match["home"].get("score", 0),
                "away_goals": match["away"].get("score", 0),
            }
            form.append(result)

        return form

    except Exception as e:
        print(f"⚠️ Sem forma para equipa {team_id}: {e}")
        return []