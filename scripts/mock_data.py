"""
Dados mock para testar o pipeline sem gastar requests à API.
Ativar em config.py: USE_MOCK = True
"""

MOCK_FIXTURES = [
    {
        "fixture_id": 1001,
        "league_id": 94,
        "league": "Liga Portugal",
        "country": "Portugal",
        "date": "20:15",
        "home_team": "Benfica",
        "home_team_id": 211,
        "away_team": "Porto",
        "away_team_id": 212,
        "status": "upcoming",
    },
    {
        "fixture_id": 1002,
        "league_id": 39,
        "league": "Premier League",
        "country": "England",
        "date": "21:00",
        "home_team": "Man City",
        "home_team_id": 50,
        "away_team": "Liverpool",
        "away_team_id": 40,
        "status": "upcoming",
    },
]

# odds 1X2 por fixture_id
MOCK_ODDS = {
    1001: {"home": 2.10, "draw": 3.40, "away": 3.20},
    1002: {"home": 1.90, "draw": 3.50, "away": 3.80},
}

# odds mercados secundários por fixture_id
MOCK_MARKET_ODDS = {
    1001: {
        "btts": {"yes": 1.75, "no": 2.05},
        "ou":   {"over": 1.80, "under": 2.00},
    },
    1002: {
        "btts": {"yes": 1.65, "no": 2.20},
        "ou":   {"over": 1.70, "under": 2.10},
    },
}

# Últimos 5 jogos por team_id
# Para o team_side="home" → os golos da equipa estão em home_goals
# Para o team_side="away" → os golos da equipa estão em away_goals
MOCK_FORM = {
    211: [  # Benfica (casa no jogo atual)
        {"home_id": 211, "away_id": 900, "home_goals": 3, "away_goals": 1, "winner": True},
        {"home_id": 211, "away_id": 901, "home_goals": 2, "away_goals": 0, "winner": True},
        {"home_id": 211, "away_id": 902, "home_goals": 1, "away_goals": 1, "winner": None},
        {"home_id": 211, "away_id": 903, "home_goals": 2, "away_goals": 1, "winner": True},
        {"home_id": 211, "away_id": 904, "home_goals": 0, "away_goals": 2, "winner": False},
    ],
    212: [  # Porto (fora no jogo atual)
        {"home_id": 900, "away_id": 212, "home_goals": 1, "away_goals": 2, "winner": False},
        {"home_id": 901, "away_id": 212, "home_goals": 0, "away_goals": 1, "winner": False},
        {"home_id": 902, "away_id": 212, "home_goals": 2, "away_goals": 2, "winner": None},
        {"home_id": 903, "away_id": 212, "home_goals": 1, "away_goals": 3, "winner": False},
        {"home_id": 904, "away_id": 212, "home_goals": 0, "away_goals": 0, "winner": None},
    ],
    50: [  # Man City (casa no jogo atual)
        {"home_id": 50, "away_id": 900, "home_goals": 4, "away_goals": 0, "winner": True},
        {"home_id": 50, "away_id": 901, "home_goals": 3, "away_goals": 1, "winner": True},
        {"home_id": 50, "away_id": 902, "home_goals": 2, "away_goals": 2, "winner": None},
        {"home_id": 50, "away_id": 903, "home_goals": 1, "away_goals": 0, "winner": True},
        {"home_id": 50, "away_id": 904, "home_goals": 2, "away_goals": 1, "winner": True},
    ],
    40: [  # Liverpool (fora no jogo atual)
        {"home_id": 900, "away_id": 40, "home_goals": 1, "away_goals": 2, "winner": False},
        {"home_id": 901, "away_id": 40, "home_goals": 0, "away_goals": 2, "winner": False},
        {"home_id": 902, "away_id": 40, "home_goals": 1, "away_goals": 1, "winner": None},
        {"home_id": 903, "away_id": 40, "home_goals": 2, "away_goals": 3, "winner": False},
        {"home_id": 904, "away_id": 40, "home_goals": 1, "away_goals": 0, "winner": True},
    ],
}
