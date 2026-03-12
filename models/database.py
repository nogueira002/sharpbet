"""
SQLite database for tracking SharpBet predictions and actual results.

Tables:
  predictions — daily tips with predicted probabilities and odds
                actual_result filled in the next day

Usage:
  from models.database import init_db, store_tip, update_result, get_performance_summary
"""

import os
import sqlite3
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "saved", "sharpbet.db")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                date          TEXT    NOT NULL,
                fixture_id    INTEGER,
                home_team     TEXT,
                away_team     TEXT,
                league        TEXT,
                market        TEXT,
                tip           TEXT,
                odd           REAL,
                edge          REAL,
                stake_pct     REAL,
                pred_home     REAL,
                pred_draw     REAL,
                pred_away     REAL,
                actual_result TEXT,    -- 'H', 'D', 'A' (filled next day)
                tip_correct   INTEGER  -- 1=correct, 0=wrong, NULL=pending
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_date    ON predictions(date)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fixture ON predictions(fixture_id)"
        )
        conn.commit()


def store_tip(tip: dict, probs: dict = None):
    """
    Store a generated tip in the database.

    tip   — the tip dict from analyze_and_generate_tips
    probs — {"home": x, "draw": y, "away": z} raw model probabilities
    """
    today = date.today().isoformat()
    probs = probs or {}

    with _connect() as conn:
        conn.execute("""
            INSERT INTO predictions
              (date, fixture_id, home_team, away_team, league,
               market, tip, odd, edge, stake_pct,
               pred_home, pred_draw, pred_away)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            today,
            tip.get("fixture_id"),
            tip.get("home_team"),
            tip.get("away_team"),
            tip.get("league"),
            tip.get("market"),
            tip.get("tip"),
            tip.get("odd"),
            tip.get("edge"),
            tip.get("stake_pct"),
            probs.get("home"),
            probs.get("draw"),
            probs.get("away"),
        ))
        conn.commit()


def update_result(fixture_id: int, actual_result: str):
    """
    Update predictions for a fixture with the actual result.
    actual_result: 'H' (home win), 'D' (draw), 'A' (away win)
    """
    # Which tip labels correspond to each result
    result_labels = {
        "H": ("Vitoria Casa",),
        "D": ("Empate",),
        "A": ("Vitoria Fora",),
    }
    market_labels = {
        "H": ("Over",),      # for O/U: can't determine from 1X2 result alone
        "D": ("Under",),
        "A": (),
    }

    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, market, tip FROM predictions "
            "WHERE fixture_id=? AND actual_result IS NULL",
            (fixture_id,)
        ).fetchall()

        for row in rows:
            tip_label = row["tip"]
            correct = 0

            if actual_result in result_labels:
                for lbl in result_labels[actual_result]:
                    if lbl in tip_label:
                        correct = 1
                        break

            conn.execute(
                "UPDATE predictions SET actual_result=?, tip_correct=? WHERE id=?",
                (actual_result, correct, row["id"])
            )
        conn.commit()


def get_performance_summary():
    """
    Returns a dict with overall performance stats.
    Only includes tips where the result is known.
    """
    with _connect() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)                                           AS total_tips,
                SUM(CASE WHEN tip_correct=1 THEN 1 ELSE 0 END)   AS wins,
                SUM(stake_pct)                                     AS total_staked,
                SUM(CASE WHEN tip_correct=1
                         THEN stake_pct * (odd - 1) ELSE 0 END)  AS gross_profit,
                SUM(CASE WHEN tip_correct=0
                         THEN stake_pct ELSE 0 END)               AS total_lost
            FROM predictions
            WHERE tip_correct IS NOT NULL
        """).fetchone()

    if not row or row["total_tips"] == 0:
        return None

    total   = row["total_tips"]
    wins    = row["wins"] or 0
    staked  = row["total_staked"] or 0
    profit  = row["gross_profit"] or 0
    lost    = row["total_lost"]   or 0
    net     = profit - lost
    roi     = (net / staked * 100) if staked > 0 else 0.0

    return {
        "total_tips":   total,
        "wins":         wins,
        "win_rate":     round(wins / total * 100, 1),
        "roi":          round(roi, 1),
        "net_profit":   round(net, 2),
        "total_staked": round(staked, 2),
    }


def get_recent_tips(days=7):
    """Return last N days of tips with results."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT date, home_team, away_team, league, market, tip,
                   odd, edge, stake_pct, actual_result, tip_correct
            FROM predictions
            ORDER BY date DESC, id DESC
            LIMIT 100
        """).fetchall()
    return [dict(r) for r in rows]
