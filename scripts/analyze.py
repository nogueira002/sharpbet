from config import (
    MIN_EDGE, MIN_FORM_GAMES,
    MIN_MODEL_PROB_1X2, MIN_MODEL_PROB_OU, MIN_MODEL_PROB_BTTS,
    MAX_ODD_1X2, MAX_ODD_OU, MAX_ODD_BTTS,
)
from scripts.fetch_fixtures import fetch_team_recent_form, fetch_standings, fetch_injuries
from models.predict import predict_match
from models.predict_markets import predict_btts, predict_ou
from models.features import build_full_features, LEAGUE_HOME_AVG, LEAGUE_AWAY_AVG
from models.database import init_db, store_tip

# Cache de standings por liga (evita requests repetidos)
_standings_cache = {}

# Kelly Criterion — fração conservadora (25% do Kelly completo)
KELLY_FRACTION = 0.25

# Elo + H2H carregados uma vez por sessão
_elo_engine = None
_h2h_index  = None


def _get_elo_engine():
    global _elo_engine
    if _elo_engine is None:
        from models.elo import EloEngine
        _elo_engine = EloEngine.load()
    return _elo_engine


def _get_h2h_index():
    global _h2h_index
    if _h2h_index is None:
        from models.h2h import build_from_history
        _h2h_index, _ = build_from_history()
    return _h2h_index


def _get_standings(league_id, season):
    key = (league_id, season)
    if key not in _standings_cache:
        _standings_cache[key] = fetch_standings(league_id, season)
    return _standings_cache[key]


def implied_probability(odd):
    if odd <= 0:
        return 0
    return 1 / odd


def kelly_stake(probability, odd, fraction=KELLY_FRACTION):
    """
    Calcula a stake óptima usando o critério de Kelly fracionado.

    Kelly completo: f* = (p × b - q) / b  onde b = odd - 1
    Kelly fracionado: f* × fraction  (mais conservador, menor variância)

    Retorna: % da banca a apostar (arredondado a 1 decimal)
    """
    if odd <= 1 or probability <= 0 or probability >= 1:
        return 0.0
    b     = odd - 1
    q     = 1 - probability
    kelly = (probability * b - q) / b
    kelly = max(0.0, kelly)
    return round(kelly * fraction * 100, 1)


def apply_injury_modifier(probs, injuries, home_team_id, away_team_id):
    """
    Ajusta ligeiramente as probabilidades com base em lesões.
    Cada jogador lesionado reduz a probabilidade da equipa em ~1%.
    Máximo de 5% de ajuste por equipa.
    """
    home_inj = min(injuries.get(home_team_id, 0), 5)
    away_inj = min(injuries.get(away_team_id, 0), 5)

    if home_inj == 0 and away_inj == 0:
        return probs

    adj_home = probs["home"] * (1 - home_inj * 0.01)
    adj_away = probs["away"] * (1 - away_inj * 0.01)
    adj_draw = probs["draw"]

    total = adj_home + adj_draw + adj_away
    return {
        "home": round(adj_home / total, 4),
        "draw": round(adj_draw / total, 4),
        "away": round(adj_away / total, 4),
    }


def find_edge(our_probs, market_odds, home_team="Casa", away_team="Fora"):
    best_edge = None
    labels    = {
        "home": f"Vitoria Casa — {home_team}",
        "draw": f"Empate",
        "away": f"Vitoria Fora — {away_team}",
    }

    for outcome in ["home", "draw", "away"]:
        odd = market_odds.get(outcome, 0)
        if odd <= 0:
            continue
        implied  = implied_probability(odd)
        our_prob = our_probs.get(outcome, 0)
        edge     = our_prob - implied

        # Filtros de qualidade: confiança mínima + limite de odd
        if our_prob < MIN_MODEL_PROB_1X2:
            continue   # modelo não está confiante o suficiente
        if odd > MAX_ODD_1X2:
            continue   # odd demasiado alta — outsider que o modelo não consegue prever

        if edge >= MIN_EDGE:
            if best_edge is None or edge > best_edge["edge"]:
                best_edge = {
                    "outcome":             outcome,
                    "label":               labels[outcome],
                    "our_probability":     round(our_prob * 100, 1),
                    "implied_probability": round(implied  * 100, 1),
                    "edge":                round(edge     * 100, 1),
                    "odd":                 odd,
                }
    return best_edge


def find_market_edge(our_prob, market_odd, label_yes, label_no):
    """
    Verifica edge num mercado binário (BTTS ou Over/Under).

    our_prob   : nossa probabilidade da opção "positiva" (0-1)
    market_odd : odd da opção "positiva"
    label_yes  : ex. "Ambas Marcam - SIM" ou "Over 2.5"
    label_no   : ex. "Ambas Marcam - NAO" ou "Under 2.5"

    Retorna dict com o melhor edge (se >= MIN_EDGE) ou None.
    """
    if not our_prob or not market_odd or market_odd <= 0:
        return None

    implied_yes = implied_probability(market_odd)
    edge_yes    = our_prob - implied_yes

    # Verificar também o lado "não"
    our_prob_no   = 1 - our_prob
    market_odd_no = market_odd  # placeholder — precisamos da odd da outra opção

    best = None
    if edge_yes >= MIN_EDGE:
        best = {
            "label":               label_yes,
            "our_probability":     round(our_prob   * 100, 1),
            "implied_probability": round(implied_yes * 100, 1),
            "edge":                round(edge_yes   * 100, 1),
            "odd":                 market_odd,
        }
    return best


def find_btts_edge(btts_probs, btts_odds):
    """Verifica edge nos dois lados do mercado BTTS."""
    if not btts_probs or not btts_odds:
        return None

    labels = {"yes": "Ambas Marcam - SIM", "no": "Ambas Marcam - NAO"}
    best = None

    for side in ["yes", "no"]:
        odd = btts_odds.get(side, 0)
        if odd <= 0:
            continue
        our_prob = btts_probs.get(side, 0)
        implied  = implied_probability(odd)
        edge     = our_prob - implied

        if our_prob < MIN_MODEL_PROB_BTTS:
            continue
        if odd > MAX_ODD_BTTS:
            continue

        if edge >= MIN_EDGE:
            if best is None or edge > best["edge"]:
                best = {
                    "label":               labels[side],
                    "our_probability":     round(our_prob * 100, 1),
                    "implied_probability": round(implied  * 100, 1),
                    "edge":                round(edge     * 100, 1),
                    "odd":                 odd,
                }
    return best


def find_ou_edge(ou_probs, ou_odds):
    """Verifica edge nos dois lados do mercado Over/Under 2.5."""
    if not ou_probs or not ou_odds:
        return None

    labels = {"over": "Over 2.5 Golos", "under": "Under 2.5 Golos"}
    best = None

    for side in ["over", "under"]:
        odd = ou_odds.get(side, 0)
        if odd <= 0:
            continue
        our_prob = ou_probs.get(side, 0)
        implied  = implied_probability(odd)
        edge     = our_prob - implied

        if our_prob < MIN_MODEL_PROB_OU:
            continue
        if odd > MAX_ODD_OU:
            continue

        if edge >= MIN_EDGE:
            if best is None or edge > best["edge"]:
                best = {
                    "label":               labels[side],
                    "our_probability":     round(our_prob * 100, 1),
                    "implied_probability": round(implied  * 100, 1),
                    "edge":                round(edge     * 100, 1),
                    "odd":                 odd,
                }
    return best


def _print_tip_block(fixture, tip_label, edge_info, stake_pct, secondary_tips=None):
    """Imprime um bloco de tip no estilo Corvo Bets."""
    W = 54
    SEP = "-" * W

    print(f"\n  {SEP}")
    print(f"  PRE-LIVE  |  {fixture['league']}  |  {fixture['date']}")
    print(f"  {fixture['home_team']} vs {fixture['away_team']}")
    print(f"  {SEP}")
    print(f"  Mercado  : {tip_label}")
    print(f"  Tip      : {edge_info['label']}")
    print(f"  Odd      : {edge_info['odd']}")
    print(f"  {'-'*W}")
    print(f"  Bookmaker: {edge_info['implied_probability']}%  -->  Modelo: {edge_info['our_probability']}%")
    print(f"  Edge     : +{edge_info['edge']}%  |  Confianca: {'Alta' if edge_info['edge'] > 10 else 'Media'}")
    print(f"  Stake    : {stake_pct}% da banca  (Kelly x{KELLY_FRACTION})")

    if secondary_tips:
        print(f"  {'-'*W}")
        print(f"  Mercados adicionais com edge:")
        for st in secondary_tips:
            print(f"    > {st['label']}  @{st['odd']}  (Modelo: {st['our_probability']}%  Edge: +{st['edge']}%)")

    print(f"  {SEP}\n")


def analyze_and_generate_tips(fixtures):
    tips = []
    _standings_cache.clear()
    init_db()  # garante que a BD existe

    elo_engine = _get_elo_engine()
    h2h_index  = _get_h2h_index()

    total = len(fixtures)
    for idx_f, fixture in enumerate(fixtures, 1):
        print(f"  [{idx_f}/{total}] {fixture['home_team']} vs {fixture['away_team']}...", end=" ", flush=True)

        h_id   = fixture["home_team_id"]
        a_id   = fixture["away_team_id"]
        h_name = fixture["home_team"]
        a_name = fixture["away_team"]

        # Forma recente (últimos 10 jogos)
        home_form_all = fetch_team_recent_form(h_id, last_n=10)
        away_form_all = fetch_team_recent_form(a_id, last_n=10)

        # Rejeitar equipas sem histórico suficiente
        if len(home_form_all) < MIN_FORM_GAMES or len(away_form_all) < MIN_FORM_GAMES:
            print(f"sem dados ({len(home_form_all)}/{len(away_form_all)} jogos)")
            continue

        # Filtrar venue-specific form localmente (sem requests extra)
        home_form_home = [m for m in home_form_all if m.get("home_id") == h_id][-5:]
        away_form_away = [m for m in away_form_all if m.get("away_id") == a_id][-5:]

        # Posição na liga (1 request por liga, com cache)
        standings = _get_standings(fixture.get("league_id"), fixture.get("season"))
        h_pos     = standings.get(h_id, 0.5)
        a_pos     = standings.get(a_id, 0.5)

        # Lesões
        injuries = fetch_injuries(fixture["fixture_id"])

        # Elo + H2H features
        elo_feats = elo_engine.get_features(h_name, a_name)
        h2h_feats = h2h_index.get_features(h_name, a_name)

        # Features completas (43 = 35 base + 8 Elo/H2H)
        features = build_full_features(
            home_form_all, home_form_home,
            away_form_all, away_form_away,
            h_id, a_id, h_pos, a_pos,
            elo_feats=elo_feats, h2h_feats=h2h_feats,
        )

        # Previsão 1X2 com ensemble XGBoost + LSTM
        our_probs = predict_match(
            home_form_all, home_form_home,
            away_form_all, away_form_away,
            h_id, a_id, h_pos, a_pos,
            elo_feats=elo_feats, h2h_feats=h2h_feats,
        )

        # Ajuste por lesões
        our_probs = apply_injury_modifier(our_probs, injuries, h_id, a_id)
        our_probs.pop("_source", None)

        # Previsões BTTS e O/U (mesmas features, 0 requests extra)
        btts_probs = predict_btts(features)
        ou_probs   = predict_ou(features)

        # Odds de mercado
        market_odds  = fixture.get("odds", {})
        market_extra = fixture.get("market_odds", {})
        btts_odds    = market_extra.get("btts") if market_extra else None
        ou_odds      = market_extra.get("ou")   if market_extra else None

        # Edge nos diferentes mercados
        edge_1x2  = find_edge(our_probs, market_odds, h_name, a_name)
        edge_btts = find_btts_edge(btts_probs, btts_odds)
        edge_ou   = find_ou_edge(ou_probs, ou_odds)

        # Tip principal: melhor edge entre 1X2, BTTS e O/U
        all_edges = []
        if edge_1x2:
            all_edges.append(("Resultado Final", edge_1x2))
        if edge_btts:
            all_edges.append(("Ambas Marcam", edge_btts))
        if edge_ou:
            all_edges.append(("Over/Under 2.5", edge_ou))

        if not all_edges:
            print("sem edge")
            continue

        print("TIP ENCONTRADA!")

        # Ordenar por edge (maior primeiro) — tip principal é a de maior edge
        all_edges.sort(key=lambda x: x[1]["edge"], reverse=True)
        primary_market, primary_edge = all_edges[0]
        secondary_edges = [e for _, e in all_edges[1:]]

        # Kelly Criterion para a tip principal
        stake_pct = kelly_stake(primary_edge["our_probability"] / 100, primary_edge["odd"])

        # Imprimir bloco de tip
        _print_tip_block(fixture, primary_market, primary_edge, stake_pct, secondary_edges)

        # Construir objeto tip
        confidence = "Alta" if primary_edge["edge"] > 10 else "Media"
        tip = {
            "fixture_id":          fixture["fixture_id"],
            "date":                fixture["date"],
            "league":              fixture["league"],
            "country":             fixture["country"],
            "home_team":           fixture["home_team"],
            "away_team":           fixture["away_team"],
            "market":              primary_market,
            "tip":                 primary_edge["label"],
            "odd":                 primary_edge["odd"],
            "our_probability":     primary_edge["our_probability"],
            "implied_probability": primary_edge["implied_probability"],
            "edge":                primary_edge["edge"],
            "stake_pct":           stake_pct,
            "confidence":          confidence,
            "secondary_tips":      secondary_edges,
        }
        tips.append(tip)

        # Guardar na BD para tracking de ROI
        store_tip(tip, probs={
            "home": our_probs.get("home"),
            "draw": our_probs.get("draw"),
            "away": our_probs.get("away"),
        })

    return tips
