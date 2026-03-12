"""
Elo rating engine for football match prediction.

Elo is calculated progressively from match history (no future leakage).
At prediction time, reflects all matches played to date.

Parameters:
  Initial rating : 1500  (all teams start equal)
  K-factor       : 20    (standard for football)
  Home advantage : +50   (virtual Elo bonus for home team)
"""

import os
import re
import json
import unicodedata
from collections import defaultdict

ELO_PATH       = os.path.join(os.path.dirname(__file__), "saved", "elo_ratings.json")
RAW_PATH       = os.path.join(os.path.dirname(__file__), "saved", "raw_fixtures.json")

INITIAL_ELO    = 1500.0
K_FACTOR       = 20.0
HOME_ADVANTAGE = 50.0   # virtual Elo bonus for home team
ELO_SCALE      = 400.0  # divisor for feature normalization


def _norm(name):
    """Normalize team name for consistent lookup."""
    nfkd = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in nfkd if not unicodedata.combining(c))
    name = re.sub(r"[^\w\s]", " ", name.lower())
    name = re.sub(r"\b(fc|afc|sc|cf|rc|ss|sd|ud|bsc|fk|bk)\b", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _expected(ra, rb):
    return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))


class EloEngine:
    """Progressive Elo calculator."""

    def __init__(self):
        self._ratings  = defaultdict(lambda: INITIAL_ELO)
        self._name_map = {}   # normalized_key -> latest team name

    def get_before(self, home_name, away_name):
        """Return current ratings WITHOUT updating (use before building features)."""
        return (
            self._ratings[_norm(home_name)],
            self._ratings[_norm(away_name)],
        )

    def update(self, home_name, away_name, home_goals, away_goals):
        """Update ratings after a completed match."""
        hk = _norm(home_name)
        ak = _norm(away_name)
        self._name_map[hk] = home_name
        self._name_map[ak] = away_name

        rh = self._ratings[hk] + HOME_ADVANTAGE
        ra = self._ratings[ak]
        eh = _expected(rh, ra)
        ea = _expected(ra, rh)

        if   home_goals > away_goals: sh, sa = 1.0, 0.0
        elif home_goals < away_goals: sh, sa = 0.0, 1.0
        else:                         sh, sa = 0.5, 0.5

        self._ratings[hk] += K_FACTOR * (sh - eh)
        self._ratings[ak] += K_FACTOR * (sa - ea)

    def get_features(self, home_name, away_name):
        """
        Returns 3 Elo features normalized to ~[-1, 1].
        Positive elo_diff = home team is stronger.
        """
        elo_h = self._ratings[_norm(home_name)]
        elo_a = self._ratings[_norm(away_name)]
        return {
            "elo_home": (elo_h - INITIAL_ELO) / ELO_SCALE,
            "elo_away": (elo_a - INITIAL_ELO) / ELO_SCALE,
            "elo_diff": (elo_h - elo_a)        / ELO_SCALE,
        }

    def save(self, path=ELO_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            k: {"rating": round(v, 2), "name": self._name_map.get(k, k)}
            for k, v in self._ratings.items()
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path=ELO_PATH):
        engine = cls()
        if not os.path.exists(path):
            return engine
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            engine._ratings[k]  = v["rating"]
            engine._name_map[k] = v.get("name", k)
        return engine

    def top_teams(self, n=20):
        return sorted(
            [(self._name_map.get(k, k), round(v, 1)) for k, v in self._ratings.items()],
            key=lambda x: -x[1],
        )[:n]


def build_from_history(raw_path=RAW_PATH):
    """
    Process all matches in raw_fixtures.json chronologically.
    Returns the final EloEngine (current ratings for all teams).
    """
    if not os.path.exists(raw_path):
        print("  raw_fixtures.json nao encontrado.")
        return EloEngine()

    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    raw_sorted = sorted(raw, key=lambda m: m["fixture"]["date"])
    engine = EloEngine()

    for match in raw_sorted:
        engine.update(
            match["teams"]["home"]["name"],
            match["teams"]["away"]["name"],
            match["goals"]["home"] or 0,
            match["goals"]["away"] or 0,
        )

    return engine


if __name__ == "__main__":
    print("A calcular Elo a partir do historico...\n")
    engine = build_from_history()
    engine.save()
    print(f"\nTop 20 equipas por Elo rating:")
    print(f"{'Equipa':<35} {'Elo':>6}")
    print("-" * 43)
    for name, rating in engine.top_teams(20):
        bar = "█" * int((rating - 1400) / 20)
        print(f"  {name:<33} {rating:>6.0f}  {bar}")
    print(f"\nElo guardado: {ELO_PATH}")
