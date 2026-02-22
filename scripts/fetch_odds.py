import requests
import time
from config import HEADERS_FOOTBALL, RAPIDAPI_HOST_FOOTBALL

def fetch_odds_for_fixtures(fixtures):
    """
    Vai buscar odds para cada fixture usando a API de futebol.
    Endpoint: football-event-odds
    """
    if not fixtures:
        return []

    fixtures_with_odds = []

    for i, fixture in enumerate(fixtures):
        fixture_id = fixture["fixture_id"]
        url = f"https://{RAPIDAPI_HOST_FOOTBALL}/football-event-odds"
        params = {
            "eventid": fixture_id,
            "countrycode": "PT"
        }

        try:
            response = requests.get(url, headers=HEADERS_FOOTBALL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            odds = extract_odds(data)
            if odds:
                fixture["odds"] = odds
                fixtures_with_odds.append(fixture)

        except Exception as e:
            # Silencioso para não encher o terminal
            pass

        # Pausa pequena para não sobrecarregar a API
        if i % 10 == 9:
            print(f"⏳ {i+1}/{len(fixtures)} processados...")
            time.sleep(0.5)

    print(f"✅ Odds encontradas para {len(fixtures_with_odds)} jogos")
    return fixtures_with_odds


def extract_odds(data):
    """
    Extrai odds 1X2 da resposta da API.
    Estrutura: response.odds.odds.matchfactMarkets[0].selections
    """
    try:
        markets = (
            data.get("response", {})
                .get("odds", {})
                .get("odds", {})
                .get("matchfactMarkets", [])
        )

        for market in markets:
            if "who_will_win" in market.get("fotMobMarketTypeId", {}).get("translationKey", ""):
                selections = market.get("selections", [])
                odds = {}

                for sel in selections:
                    name = sel.get("name", "").lower()
                    try:
                        val = float(sel.get("oddsDecimal", 0))
                    except:
                        val = 0

                    if name == "1":
                        odds["home"] = val
                    elif name == "x":
                        odds["draw"] = val
                    elif name == "2":
                        odds["away"] = val

                if odds.get("home") and odds.get("away"):
                    return odds

    except Exception:
        return None

    return None