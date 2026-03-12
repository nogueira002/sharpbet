"""
Feature engineering — converte dados de jogos em números para o modelo.

Versão 4: 43 features por jogo

Por equipa (13 × 2 = 26):
  1.  win_rate           — taxa de vitórias (últimos 10 jogos)
  2.  draw_rate          — taxa de empates (últimos 10 jogos)
  3.  avg_scored         — média de golos marcados (últimos 10)
  4.  avg_conceded       — média de golos sofridos (últimos 10)
  5.  goal_diff          — diferença média de golos (últimos 10)
  6.  clean_sheet_rate   — jogos sem sofrer golos (últimos 10)
  7.  scored_2plus_rate  — jogos com 2+ golos marcados (últimos 10)
  8.  last3_win_rate     — taxa de vitórias últimos 3 (momentum)
  9.  last3_avg_scored   — média de golos últimos 3
  10. venue_win_rate     — vitórias em casa/fora (últimos 5 na venue)
  11. venue_avg_scored   — golos marcados na venue (últimos 5)
  12. venue_avg_conceded — golos sofridos na venue (últimos 5)
  13. position_norm      — posição na liga normalizada (0=1º, 1=último)

Poisson/xG (9 features de jogo):
  14. home_attack_str    — força de ataque da casa vs liga
  15. home_defense_str   — força de defesa da casa vs liga
  16. away_attack_str    — força de ataque de fora vs liga
  17. away_defense_str   — força de defesa de fora vs liga
  18. xg_home           — golos esperados casa (Expected Goals)
  19. xg_away           — golos esperados fora
  20. poisson_home      — P(vitória casa) via distribuição de Poisson
  21. poisson_draw      — P(empate) via Poisson
  22. poisson_away      — P(vitória fora) via Poisson
"""

import math

# Médias típicas de golos nas ligas europeias de topo
LEAGUE_HOME_AVG = 1.35
LEAGUE_AWAY_AVG = 1.10

NEUTRAL_FEATURES = {
    "win_rate": 0.33, "draw_rate": 0.25,
    "avg_scored": 1.2, "avg_conceded": 1.2, "goal_diff": 0.0,
    "clean_sheet_rate": 0.2, "scored_2plus_rate": 0.3,
    "last3_win_rate": 0.33, "last3_avg_scored": 1.2,
    "venue_win_rate": 0.33, "venue_avg_scored": 1.2, "venue_avg_conceded": 1.2,
}

FEAT_ORDER = [
    "win_rate", "draw_rate", "avg_scored", "avg_conceded", "goal_diff",
    "clean_sheet_rate", "scored_2plus_rate", "last3_win_rate", "last3_avg_scored",
    "venue_win_rate", "venue_avg_scored", "venue_avg_conceded",
]

POISSON_FEAT_NAMES = [
    "home_attack_str", "home_defense_str",
    "away_attack_str", "away_defense_str",
    "xg_home", "xg_away",
    "poisson_home", "poisson_draw", "poisson_away",
]

# ── Elo + H2H feature names (8 features) ──────────────────────────────────
ELO_H2H_FEAT_NAMES = [
    "elo_home", "elo_away", "elo_diff",           # 3 Elo features
    "h2h_home_wins", "h2h_draws", "h2h_away_wins", # 3 H2H result features
    "h2h_avg_goals", "h2h_count",                  # 2 H2H volume features
]

ELO_H2H_NEUTRAL = {
    "elo_home":      0.0,   "elo_away":      0.0,   "elo_diff":      0.0,
    "h2h_home_wins": 0.33,  "h2h_draws":     0.33,  "h2h_away_wins": 0.33,
    "h2h_avg_goals": 0.50,  "h2h_count":     0.0,
}


# ──────────────────────────────────────────────
# Form features
# ──────────────────────────────────────────────

def _stats_from_form(form, team_id):
    if not form:
        return None
    n = len(form)
    wins = draws = scored = conceded = clean = two_plus = 0
    for match in form:
        is_home = match.get("home_id") == team_id
        g  = match["home_goals"] if is_home else match["away_goals"]
        gc = match["away_goals"] if is_home else match["home_goals"]
        w  = match["winner"]
        won  = (w is True and is_home) or (w is False and not is_home)
        drew = w is None
        scored += g; conceded += gc
        if gc == 0: clean    += 1
        if g >= 2:  two_plus += 1
        if won:  wins  += 1
        if drew: draws += 1
    return {
        "win_rate":          wins    / n,
        "draw_rate":         draws   / n,
        "avg_scored":        scored  / n,
        "avg_conceded":      conceded / n,
        "goal_diff":         (scored - conceded) / n,
        "clean_sheet_rate":  clean    / n,
        "scored_2plus_rate": two_plus / n,
    }


def compute_team_features(form_overall, form_venue, team_id, position_norm=0.5):
    overall = _stats_from_form(form_overall, team_id) or NEUTRAL_FEATURES
    last3   = _stats_from_form((form_overall or [])[-3:], team_id) or NEUTRAL_FEATURES
    venue   = _stats_from_form(form_venue, team_id) or overall

    return {
        "win_rate":           overall["win_rate"],
        "draw_rate":          overall["draw_rate"],
        "avg_scored":         overall["avg_scored"],
        "avg_conceded":       overall["avg_conceded"],
        "goal_diff":          overall["goal_diff"],
        "clean_sheet_rate":   overall["clean_sheet_rate"],
        "scored_2plus_rate":  overall["scored_2plus_rate"],
        "last3_win_rate":     last3["win_rate"],
        "last3_avg_scored":   last3["avg_scored"],
        "venue_win_rate":     venue["win_rate"],
        "venue_avg_scored":   venue["avg_scored"],
        "venue_avg_conceded": venue["avg_conceded"],
        "position_norm":      position_norm,
    }


# ──────────────────────────────────────────────
# Poisson / xG features
# ──────────────────────────────────────────────

def _poisson_prob(lam, k):
    """P(X=k) onde X ~ Poisson(lam)"""
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _match_probs_poisson(lambda_home, lambda_away, max_goals=8):
    """
    Calcula P(casa), P(empate), P(fora) usando distribuição de Poisson.

    Para cada combinação de golos (h, a) até max_goals:
      P(h, a) = Poisson(lambda_home, h) × Poisson(lambda_away, a)
    """
    p_home = p_draw = p_away = 0.0
    for h in range(max_goals + 1):
        ph = _poisson_prob(lambda_home, h)
        for a in range(max_goals + 1):
            p = ph * _poisson_prob(lambda_away, a)
            if   h > a: p_home += p
            elif h == a: p_draw += p
            else:        p_away += p
    return p_home, p_draw, p_away


def compute_poisson_features(
    home_form_home, away_form_away,
    home_team_id, away_team_id,
    league_home_avg=LEAGUE_HOME_AVG,
    league_away_avg=LEAGUE_AWAY_AVG,
):
    """
    Calcula 9 features baseadas no modelo de Poisson (Dixon-Coles simplificado).

    Força de ataque = media golos marcados / media da liga
    Força de defesa = media golos sofridos / media da liga (>1 = defesa fraca)

    xG casa = ataque_casa × defesa_fora × media_liga_casa
    xG fora = ataque_fora × defesa_casa × media_liga_fora

    P(casa/empate/fora) = integral da distribuição de Poisson
    """
    def avg_goals(form, team_id, scored=True):
        if not form:
            return None
        total = 0
        for m in form:
            is_home = m.get("home_id") == team_id
            if scored:
                total += m["home_goals"] if is_home else m["away_goals"]
            else:
                total += m["away_goals"] if is_home else m["home_goals"]
        return total / len(form)

    h_scored   = avg_goals(home_form_home, home_team_id, scored=True)  or league_home_avg
    h_conceded = avg_goals(home_form_home, home_team_id, scored=False) or league_away_avg
    a_scored   = avg_goals(away_form_away, away_team_id, scored=True)  or league_away_avg
    a_conceded = avg_goals(away_form_away, away_team_id, scored=False) or league_home_avg

    # Forças relativas à liga
    home_attack  = h_scored   / max(league_home_avg, 0.01)
    home_defense = h_conceded / max(league_away_avg, 0.01)
    away_attack  = a_scored   / max(league_away_avg, 0.01)
    away_defense = a_conceded / max(league_home_avg, 0.01)

    # Golos esperados (Expected Goals)
    xg_home = max(0.1, min(home_attack * away_defense * league_home_avg, 8.0))
    xg_away = max(0.1, min(away_attack * home_defense * league_away_avg, 8.0))

    # Probabilidades via Poisson
    p_home, p_draw, p_away = _match_probs_poisson(xg_home, xg_away)

    return {
        "home_attack_str": round(home_attack,  4),
        "home_defense_str":round(home_defense, 4),
        "away_attack_str": round(away_attack,  4),
        "away_defense_str":round(away_defense, 4),
        "xg_home":         round(xg_home,      4),
        "xg_away":         round(xg_away,      4),
        "poisson_home":    round(p_home,        4),
        "poisson_draw":    round(p_draw,        4),
        "poisson_away":    round(p_away,        4),
    }


# ──────────────────────────────────────────────
# Vector final de features
# ──────────────────────────────────────────────

def build_match_features(
    home_form_all, home_form_home,
    away_form_all, away_form_away,
    home_team_id=None, away_team_id=None,
    home_position_norm=0.5, away_position_norm=0.5,
    league_home_avg=LEAGUE_HOME_AVG, league_away_avg=LEAGUE_AWAY_AVG,
):
    """
    Combina todas as features num vetor de 35 números para o XGBoost.

    26 features de forma (13 por equipa) + 9 features Poisson = 35
    """
    home_feats    = compute_team_features(home_form_all, home_form_home, home_team_id, home_position_norm)
    away_feats    = compute_team_features(away_form_all, away_form_away, away_team_id, away_position_norm)
    poisson_feats = compute_poisson_features(
        home_form_home, away_form_away, home_team_id, away_team_id,
        league_home_avg, league_away_avg,
    )

    return (
        [home_feats[f] for f in FEAT_ORDER] + [home_feats["position_norm"]] +
        [away_feats[f] for f in FEAT_ORDER] + [away_feats["position_norm"]] +
        [poisson_feats[f] for f in POISSON_FEAT_NAMES]
    )


# Nomes das 35 features base para o CSV (backwards compat)
FEATURE_NAMES = (
    [f"home_{f}" for f in FEAT_ORDER] + ["home_position_norm"] +
    [f"away_{f}" for f in FEAT_ORDER] + ["away_position_norm"] +
    POISSON_FEAT_NAMES +
    ["result"]
)

# ── Feature vector completo: 35 base + 8 Elo/H2H = 43 features ───────────

def build_full_features(
    home_form_all, home_form_home,
    away_form_all, away_form_away,
    home_team_id=None, away_team_id=None,
    home_position_norm=0.5, away_position_norm=0.5,
    league_home_avg=LEAGUE_HOME_AVG, league_away_avg=LEAGUE_AWAY_AVG,
    elo_feats=None, h2h_feats=None,
):
    """
    Combina todas as features num vetor de 43 números.

    35 base (forma + Poisson) + 3 Elo + 5 H2H = 43
    Se elo_feats/h2h_feats forem None, usa valores neutros.
    """
    base = build_match_features(
        home_form_all, home_form_home,
        away_form_all, away_form_away,
        home_team_id, away_team_id,
        home_position_norm, away_position_norm,
        league_home_avg, league_away_avg,
    )

    ef = elo_feats if elo_feats is not None else ELO_H2H_NEUTRAL
    hf = h2h_feats if h2h_feats is not None else ELO_H2H_NEUTRAL

    return base + [ef.get(n, ELO_H2H_NEUTRAL[n]) for n in ELO_H2H_FEAT_NAMES]


# Nomes das 43 features para o CSV v2
FULL_FEATURE_NAMES = (
    [f"home_{f}" for f in FEAT_ORDER] + ["home_position_norm"] +
    [f"away_{f}" for f in FEAT_ORDER] + ["away_position_norm"] +
    POISSON_FEAT_NAMES +
    ELO_H2H_FEAT_NAMES +
    ["result"]
)
