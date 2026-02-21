# SharpBet

A Python pipeline that identifies value bets in football matches by comparing model-estimated probabilities against bookmaker odds.

## How it works

1. **Fetch fixtures** (`scripts/fetch_fixtures.py`) — Calls the RapidAPI football data API to get today's matches and each team's recent form (last 5 games).

2. **Fetch odds** (`scripts/fetch_odds.py`) — For each fixture, fetches prematch 1X2 odds from the odds feed API and extracts the best available price for Home / Draw / Away.

3. **Analyse & generate tips** (`scripts/analyze.py`) — Estimates win probabilities from team form scores, computes the edge against implied market probabilities, and flags bets where the edge exceeds the configured minimum (default 5%).

4. **Scheduler** (`main.py`) — Runs the full pipeline immediately on start, then schedules it to repeat daily at 08:00.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file with your RapidAPI key:

```
RAPIDAPI_KEY=your_key_here
```

## Run

```bash
python main.py
```

## Configuration

Edit `config.py` to adjust:

| Variable | Default | Description |
|---|---|---|
| `MIN_EDGE` | `0.05` | Minimum edge (5%) to generate a tip |
| `FREE_TIER_TIPS_PER_DAY` | `1` | Max tips per day on free plan |
| `FREE_TIER_DELAY_MINUTES` | `60` | Delay for free-tier users |

## Project structure

```
SharpBet/
├── main.py              # Entry point + scheduler
├── config.py            # API keys and constants
├── requirements.txt
└── scripts/
    ├── fetch_fixtures.py  # Today's fixtures + team form
    ├── fetch_odds.py      # 1X2 odds per fixture
    └── analyze.py         # Edge calculation + tip generation
```
