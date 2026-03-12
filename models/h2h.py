"""
Head-to-head statistics index.

Builds a lookup table from match history:
  For each team pair, stores last 5 H2H results.
  Features: home win rate, draw rate, away win rate, avg goals, count.
"""

import os
import re
import json
import unicodedata
from collections import defaultdict

RAW_PATH = os.path.join(os.path.dirname(__file__), "saved", "raw_fixtures.json")
H2H_MAXN = 5   # last N H2H meetings to consider

# Neutral values used when no H2H history exists
H2H_NEUTRAL = {
    "h2h_home_wins":  0.33,
    "h2h_draws":      0.33,
    "h2h_away_wins":  0.33,
    "h2h_avg_goals":  0.50,   # normalized: 2.5 goals / 5
    "h2h_count":      0.0,
}


def _norm(name):
    nfkd = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in nfkd if not unicodedata.combining(c))
    name = re.sub(r"[^\w\s]", " ", name.lower())
    name = re.sub(r"\b(fc|afc|sc|cf|rc|ss|sd|ud|bsc|fk|bk)\b", " ", name)
    return re.sub(r"\s+", " ", name).strip()


class H2HIndex:
    """Lookup index for head-to-head statistics."""

    def __init__(self):
        # key: frozenset({norm_a, norm_b})
        # value: list of {"h": norm_home, "a": norm_away, "hg": int, "ag": int}
        self._data = defaultdict(list)

    def add(self, home_name, away_name, home_goals, away_goals):
        """Record a completed match."""
        h = _norm(home_name)
        a = _norm(away_name)
        self._data[frozenset([h, a])].append({
            "h": h, "a": a, "hg": home_goals, "ag": away_goals,
        })

    def get_features(self, home_name, away_name):
        """
        Returns 5 H2H features from the perspective of the current home team.
        Uses last H2H_MAXN meetings only.
        """
        h = _norm(home_name)
        a = _norm(away_name)
        all_matches = self._data.get(frozenset([h, a]), [])
        recent = all_matches[-H2H_MAXN:]

        if not recent:
            return dict(H2H_NEUTRAL)

        n = len(recent)
        home_wins = draws = away_wins = total_goals = 0

        for m in recent:
            # Adjust to current home team perspective
            hg, ag = (m["hg"], m["ag"]) if m["h"] == h else (m["ag"], m["hg"])
            if   hg > ag: home_wins += 1
            elif hg == ag: draws    += 1
            else:          away_wins += 1
            total_goals += hg + ag

        return {
            "h2h_home_wins":  home_wins  / n,
            "h2h_draws":      draws      / n,
            "h2h_away_wins":  away_wins  / n,
            "h2h_avg_goals":  min((total_goals / n) / 5.0, 1.0),
            "h2h_count":      min(n, H2H_MAXN) / H2H_MAXN,
        }


def build_from_history(raw_path=RAW_PATH):
    """
    Build the H2H index from all available history.
    Returns (index, fixture_h2h) where fixture_h2h maps
    fixture_id -> features BEFORE that match was added (no leakage).
    """
    if not os.path.exists(raw_path):
        return H2HIndex(), {}

    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    raw_sorted = sorted(raw, key=lambda m: m["fixture"]["date"])
    idx        = H2HIndex()
    fixture_h2h = {}

    for match in raw_sorted:
        h_name = match["teams"]["home"]["name"]
        a_name = match["teams"]["away"]["name"]
        hg     = match["goals"]["home"] or 0
        ag     = match["goals"]["away"] or 0
        fid    = match["fixture"]["id"]

        # Features BEFORE this match (no leakage)
        fixture_h2h[fid] = idx.get_features(h_name, a_name)
        idx.add(h_name, a_name, hg, ag)

    return idx, fixture_h2h
