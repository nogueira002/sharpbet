import requests
from config import HEADERS_ODDS, RAPIDAPI_HOST_ODDS

def fetch_odds_for_fixtures(fixtures):
    """
    Para cada fixture, vai buscar as odds do mercado 1X2.
    Adiciona as odds ao objeto do fixture.
    """
    fixtures_with_odds = []

    for fixture in fixtures:
        fixture_id = fixture["fixture_id"]
        url = f"https://{RAPIDAPI_HOST_ODDS}/api/v1/markets/feed"

        params = {
            "placing": "PREMATCH",
            "market_name": "1X2",
            "bet_type": "BACK",
            "event_ids": str(fixture_id),
            "period": "FULL_TIME_AND_OT",
            "page": 0,
        }

        try:
            response = requests.get(url, headers=HEADERS_ODDS, params=params)
            response.raise_for_status()
            data = response.json()

            odds = extract_best_odds(data)
            if odds:
                fixture["odds"] = odds
                fixtures_with_odds.append(fixture)

        except Exception as e:
            print(f"⚠️ Sem odds para fixture {fixture_id}: {e}")
            continue

    print(f"📊 Odds obtidas para {len(fixtures_with_odds)} jogos")
    return fixtures_with_odds


def extract_best_odds(data):
    """
    Extrai as melhores odds disponíveis para Casa/Empate/Fora.
    Retorna dict com as melhores odds de cada mercado.
    """
    best_odds = {"home": 0, "draw": 0, "away": 0}

    try:
        markets = data.get("markets", [])
        for market in markets:
            for selection in market.get("selections", []):
                name = selection.get("name", "").lower()
                price = selection.get("price", 0)

                if "home" in name or "1" == name:
                    best_odds["home"] = max(best_odds["home"], price)
                elif "draw" in name or "x" == name:
                    best_odds["draw"] = max(best_odds["draw"], price)
                elif "away" in name or "2" == name:
                    best_odds["away"] = max(best_odds["away"], price)

    except Exception as e:
        print(f"⚠️ Erro ao extrair odds: {e}")
        return None

    # Só retorna se tiver odds válidas
    if best_odds["home"] > 0 and best_odds["away"] > 0:
        return best_odds

    return None