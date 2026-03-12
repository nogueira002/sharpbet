import re
import difflib
import unicodedata
from datetime import datetime, timezone
from config import USE_MOCK, odds_api_get, SUPPORTED_COMPETITIONS


# ── Normalização de nomes de equipas ──────────────────────────────────────

def normalize_team_name(name):
    """
    Normaliza nome de equipa para comparação fuzzy:
    - Remove acentos
    - Lowercase
    - Remove pontuação
    - Remove sufixos comuns (FC, AFC, SC, ...)
    """
    # Remover acentos
    nfkd = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Lowercase + remover pontuação
    name = re.sub(r"[^\w\s]", " ", name.lower())
    # Remover sufixos/prefixos de clube
    name = re.sub(r"\b(fc|afc|sc|cf|rc|ss|sd|ud|bsc|fk|bk)\b", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _team_similarity(a, b):
    """Score 0-1 de semelhança entre dois nomes de equipa."""
    na = normalize_team_name(a)
    nb = normalize_team_name(b)

    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.9

    # Overlap de palavras significativas (>2 chars)
    wa = {w for w in na.split() if len(w) > 2}
    wb = {w for w in nb.split() if len(w) > 2}
    if wa and wb:
        shorter = wa if len(wa) <= len(wb) else wb
        longer  = wb if len(wa) <= len(wb) else wa
        if shorter and shorter.issubset(longer):
            return 0.85

    return difflib.SequenceMatcher(None, na, nb).ratio()


def _find_matching_event(home_team, away_team, events):
    """
    Encontra o evento da Odds API que melhor corresponde a um fixture.
    Ignora eventos que já começaram (commence_time no passado).
    """
    now_utc = datetime.now(timezone.utc)
    best_score = 0.0
    best_event = None
    for event in events:
        # Ignorar jogos que já começaram — odds em tempo real não servem
        commence_str = event.get("commence_time", "")
        if commence_str:
            try:
                commence_dt = datetime.fromisoformat(commence_str.replace("Z", "+00:00"))
                if commence_dt < now_utc:
                    continue
            except ValueError:
                pass

        sh = _team_similarity(home_team, event["home_team"])
        sa = _team_similarity(away_team, event["away_team"])
        score = (sh + sa) / 2
        if score > best_score and score > 0.65:
            best_score = score
            best_event = event
    return best_event


# ── Extração de odds ───────────────────────────────────────────────────────

def _extract_h2h_odds(event, home_team, away_team):
    """
    Extrai odds 1X2 do evento da Odds API.
    A equipa com maior semelhança ao home_team recebe a odd "home".
    """
    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market["key"] != "h2h":
                continue
            outcomes = market["outcomes"]
            if len(outcomes) != 3:
                continue

            odds = {}
            for outcome in outcomes:
                name  = outcome["name"]
                price = float(outcome["price"])
                if name == "Draw":
                    odds["draw"] = price
                elif _team_similarity(home_team, name) >= _team_similarity(away_team, name):
                    odds["home"] = price
                else:
                    odds["away"] = price

            if odds.get("home") and odds.get("draw") and odds.get("away"):
                return odds
    return None


def _extract_market_odds(event):
    """
    Extrai odds BTTS e Over/Under 2.5.

    Retorna: {
        "btts": {"yes": 1.85, "no": 1.95},   # ou None
        "ou":   {"over": 1.80, "under": 2.00} # ou None
    }
    """
    result = {"btts": None, "ou": None}

    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            key = market["key"]

            if key == "btts" and result["btts"] is None:
                btts = {}
                for o in market["outcomes"]:
                    n = o["name"].lower()
                    if n == "yes":
                        btts["yes"] = float(o["price"])
                    elif n == "no":
                        btts["no"] = float(o["price"])
                if btts.get("yes") and btts.get("no"):
                    result["btts"] = btts

            elif key == "totals" and result["ou"] is None:
                ou = {}
                for o in market["outcomes"]:
                    if float(o.get("point", 0)) != 2.5:
                        continue
                    n = o["name"].lower()
                    if n == "over":
                        ou["over"] = float(o["price"])
                    elif n == "under":
                        ou["under"] = float(o["price"])
                if ou.get("over") and ou.get("under"):
                    result["ou"] = ou

        if result["btts"] and result["ou"]:
            break

    return result


# ── Função principal ───────────────────────────────────────────────────────

def fetch_odds_for_fixtures(fixtures):
    """
    Vai buscar odds da The Odds API para cada fixture.

    Estratégia eficiente:
    - 1 request por liga (retorna todos os jogos da liga de uma vez)
    - Depois faz match por nome de equipa (fuzzy matching)

    Custo: ~3 créditos por liga (h2h + btts + totals × 1 região)
    """
    if not fixtures:
        return []

    if USE_MOCK:
        from scripts.mock_data import MOCK_ODDS, MOCK_MARKET_ODDS
        result = []
        for fixture in fixtures:
            odds = MOCK_ODDS.get(fixture["fixture_id"])
            if odds:
                fixture["odds"] = odds
                fixture["market_odds"] = MOCK_MARKET_ODDS.get(fixture["fixture_id"], {})
                result.append(fixture)
        return result

    # Agrupar fixtures por sport key
    sport_key_to_fixtures = {}
    for fixture in fixtures:
        comp_code = fixture.get("league_id", "")
        odds_key  = SUPPORTED_COMPETITIONS.get(comp_code, {}).get("odds_key")
        if odds_key:
            sport_key_to_fixtures.setdefault(odds_key, []).append(fixture)

    # 1 request por liga → todos os jogos futuros dessa liga com odds
    sport_events = {}
    for sport_key in sport_key_to_fixtures:
        try:
            r = odds_api_get(f"/sports/{sport_key}/odds", {
                "regions":    "eu",
                "markets":    "h2h,totals",
                "oddsFormat": "decimal",
            })
            sport_events[sport_key] = r.json()
        except Exception as e:
            print(f"  [!] Odds indisponíveis para {sport_key}: {e}")
            sport_events[sport_key] = []

    # Fazer match de cada fixture com o seu evento na Odds API
    result = []
    for sport_key, sport_fixtures in sport_key_to_fixtures.items():
        events = sport_events.get(sport_key, [])
        for fixture in sport_fixtures:
            event = _find_matching_event(
                fixture["home_team"], fixture["away_team"], events
            )
            if event is None:
                continue
            odds = _extract_h2h_odds(event, fixture["home_team"], fixture["away_team"])
            if not odds:
                continue
            fixture["odds"]        = odds
            fixture["market_odds"] = _extract_market_odds(event)
            result.append(fixture)

    print(f"[Odds API] {len(result)}/{len(fixtures)} jogos com odds")
    return result
