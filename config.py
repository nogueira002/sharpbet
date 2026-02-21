import os
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST_FOOTBALL = "free-api-live-football-data.p.rapidapi.com"
RAPIDAPI_HOST_ODDS = "odds-feed.p.rapidapi.com"

HEADERS_FOOTBALL = {
    "x-rapidapi-host": RAPIDAPI_HOST_FOOTBALL,
    "x-rapidapi-key": RAPIDAPI_KEY,
}

HEADERS_ODDS = {
    "x-rapidapi-host": RAPIDAPI_HOST_ODDS,
    "x-rapidapi-key": RAPIDAPI_KEY,
}

# Edge mínimo para gerar tip (ex: 0.05 = 5%)
MIN_EDGE = 0.05

# Quantas tips máximo por dia no plano free
FREE_TIER_TIPS_PER_DAY = 1

# Delay em minutos para utilizadores free
FREE_TIER_DELAY_MINUTES = 60