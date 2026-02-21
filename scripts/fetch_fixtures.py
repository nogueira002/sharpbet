import requests
from datetime import datetime
from config import HEADERS_FOOTBALL, RAPIDAPI_HOST_FOOTBALL

def fetch_todays_fixtures():
    """
    Vai buscar todos os jogos de hoje à API.
    Retorna lista de fixtures com info básica.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://{RAPIDAPI_HOST_FOOTBALL}/football-get-fixtures-by-date"

    params = {"date": today}

    try:
        response = requests.get(url, headers=HEADERS_FOOTBALL, params=params)
        response.raise_for_status()
        data = response.json()

        fixtures = []
        for match in data.get("response", []):
            fixture = {
                "fixture_id": match["fixture"]["id"],
                "date": match["fixture"]["date"],
                "league": match["league"]["name"],
                "country": match["league"]["country"],
                "home_team": match["teams"]["home"]["name"],
                "home_team_id": match["teams"]["home"]["id"],
                "away_team": match["teams"]["away"]["name"],
                "away_team_id": match["teams"]["away"]["id"],
                "venue": match["fixture"].get("venue", {}).get("name", "N/A"),
            }
            fixtures.append(fixture)

        print(f"📅 {len(fixtures)} jogos encontrados para {today}")
        return fixtures

    except Exception as e:
        print(f"❌ Erro ao recolher fixtures: {e}")
        return []


def fetch_team_recent_form(team_id, last_n=5):
    """
    Vai buscar os últimos N jogos de uma equipa.
    """
    url = f"https://{RAPIDAPI_HOST_FOOTBALL}/football-get-team-fixtures"
    params = {"teamId": team_id, "last": last_n}

    try:
        response = requests.get(url, headers=HEADERS_FOOTBALL, params=params)
        response.raise_for_status()
        data = response.json()

        form = []
        for match in data.get("response", []):
            result = {
                "date": match["fixture"]["date"],
                "home": match["teams"]["home"]["name"],
                "away": match["teams"]["away"]["name"],
                "home_goals": match["goals"]["home"],
                "away_goals": match["goals"]["away"],
                "winner": match["teams"]["home"]["winner"],
            }
            form.append(result)

        return form

    except Exception as e:
        print(f"❌ Erro ao recolher forma da equipa {team_id}: {e}")
        return []