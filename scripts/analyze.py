from config import MIN_EDGE
from scripts.fetch_fixtures import fetch_team_recent_form

def implied_probability(odd):
    """Converte odd decimal para probabilidade implícita."""
    if odd <= 0:
        return 0
    return 1 / odd

def calculate_form_score(form, team_side):
    """
    Calcula score de forma baseado nos últimos jogos.
    Retorna valor entre 0 e 1.
    """
    if not form:
        return 0.5  # Neutro se não houver dados

    wins = 0
    draws = 0
    goals_scored = 0
    goals_conceded = 0

    for match in form:
        is_home = team_side == "home"
        scored = match["home_goals"] if is_home else match["away_goals"]
        conceded = match["away_goals"] if is_home else match["home_goals"]
        winner = match["winner"]  # True=home won, False=away won, None=draw

        goals_scored += scored or 0
        goals_conceded += conceded or 0

        if winner is None:
            draws += 1
        elif (winner is True and is_home) or (winner is False and not is_home):
            wins += 1

    n = len(form)
    win_rate = wins / n
    draw_rate = draws / n
    avg_goals = goals_scored / n
    avg_conceded = goals_conceded / n

    # Score composto
    score = (win_rate * 0.5) + (draw_rate * 0.1) + (min(avg_goals, 3) / 3 * 0.25) - (min(avg_conceded, 3) / 3 * 0.15)
    return max(0, min(1, score))


def estimate_probabilities(home_form_score, away_form_score):
    """
    Estima probabilidades do nosso modelo (simples por agora).
    Fase 1: baseado em forma recente.
    Fase 2: será substituído por XGBoost + LSTM.
    """
    total = home_form_score + away_form_score + 0.3  # 0.3 = peso do empate

    prob_home = home_form_score / total
    prob_draw = 0.3 / total
    prob_away = away_form_score / total

    return {
        "home": round(prob_home, 4),
        "draw": round(prob_draw, 4),
        "away": round(prob_away, 4),
    }


def find_edge(our_probs, market_odds):
    """
    Compara as nossas probabilidades com as odds do mercado.
    Retorna o melhor edge encontrado, se existir.
    """
    best_edge = None

    outcomes = ["home", "draw", "away"]
    labels = {"home": "Vitória Casa", "draw": "Empate", "away": "Vitória Fora"}

    for outcome in outcomes:
        odd = market_odds.get(outcome, 0)
        if odd <= 0:
            continue

        implied_prob = implied_probability(odd)
        our_prob = our_probs.get(outcome, 0)
        edge = our_prob - implied_prob

        if edge >= MIN_EDGE:
            if best_edge is None or edge > best_edge["edge"]:
                best_edge = {
                    "outcome": outcome,
                    "label": labels[outcome],
                    "our_probability": round(our_prob * 100, 1),
                    "implied_probability": round(implied_prob * 100, 1),
                    "edge": round(edge * 100, 1),
                    "odd": odd,
                }

    return best_edge


def analyze_and_generate_tips(fixtures):
    """
    Analisa cada fixture e gera tips onde existe edge positivo.
    """
    tips = []

    for fixture in fixtures:
        print(f"🔍 A analisar: {fixture['home_team']} vs {fixture['away_team']}")

        # Recolhe forma recente das duas equipas
        home_form = fetch_team_recent_form(fixture["home_team_id"])
        away_form = fetch_team_recent_form(fixture["away_team_id"])

        # Calcula scores de forma
        home_score = calculate_form_score(home_form, "home")
        away_score = calculate_form_score(away_form, "away")

        # Estima probabilidades
        our_probs = estimate_probabilities(home_score, away_score)

        # Encontra edge
        edge = find_edge(our_probs, fixture["odds"])

        if edge:
            tip = {
                "fixture_id": fixture["fixture_id"],
                "date": fixture["date"],
                "league": fixture["league"],
                "country": fixture["country"],
                "home_team": fixture["home_team"],
                "away_team": fixture["away_team"],
                "tip": edge["label"],
                "outcome": edge["outcome"],
                "odd": edge["odd"],
                "our_probability": edge["our_probability"],
                "implied_probability": edge["implied_probability"],
                "edge": edge["edge"],
                "confidence": "Alta" if edge["edge"] > 10 else "Média",
            }
            tips.append(tip)
            print(f"✅ TIP: {fixture['home_team']} vs {fixture['away_team']} → {edge['label']} @ {edge['odd']} (Edge: +{edge['edge']}%)")
        else:
            print(f"❌ Sem edge suficiente")

    return tips