import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ── football-data.org (fixtures, forma, standings — ilimitado) ─────────────
FOOTBALLDATA_KEY      = os.getenv("FOOTBALLDATA_KEY")
FOOTBALLDATA_BASE_URL = "https://api.football-data.org/v4"
FOOTBALLDATA_HEADERS  = {"X-Auth-Token": FOOTBALLDATA_KEY}

# ── The Odds API (1X2 + BTTS + O/U — 500 créditos/mês) ────────────────────
ODDS_API_KEY      = os.getenv("ODDS_API_KEY")
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"

# ── App config ─────────────────────────────────────────────────────────────
USE_MOCK        = False
TEST_MODE_LIMIT = 0
MIN_EDGE        = 0.08    # edge mínimo (era 0.05) — mais exigente
MIN_FORM_GAMES  = 3
KELLY_FRACTION  = 0.25

# ── Filtros de qualidade — probabilidade mínima do modelo ──────────────────
# O modelo só gera tip quando tem esta confiança mínima no resultado previsto.
# Isto elimina apostas em outsiders onde o modelo tem 25-35% de confiança.
MIN_MODEL_PROB_1X2  = 0.55   # 1X2: modelo deve dizer ≥55% para o resultado
MIN_MODEL_PROB_OU   = 0.58   # O/U: modelo deve dizer ≥58% para over/under
MIN_MODEL_PROB_BTTS = 0.60   # BTTS: modelo deve dizer ≥60% (mercado mais incerto)

# ── Limites de odds — evitar outsiders que o modelo não consegue prever ────
MAX_ODD_1X2  = 3.0   # não apostar em 1X2 com odd acima de 3.0
MAX_ODD_OU   = 2.5   # não apostar em O/U com odd acima de 2.5
MAX_ODD_BTTS = 2.2   # não apostar em BTTS com odd acima de 2.2

# ── Competições suportadas (free tier football-data.org) ───────────────────
# Chave: código da competição no football-data.org
# odds_key: sport key correspondente na The Odds API (None = sem odds)
SUPPORTED_COMPETITIONS = {
    "PL":  {"name": "Premier League",  "country": "England",     "odds_key": "soccer_epl"},
    "PD":  {"name": "La Liga",         "country": "Spain",       "odds_key": "soccer_spain_la_liga"},
    "BL1": {"name": "Bundesliga",      "country": "Germany",     "odds_key": "soccer_germany_bundesliga"},
    "SA":  {"name": "Serie A",         "country": "Italy",       "odds_key": "soccer_italy_serie_a"},
    "FL1": {"name": "Ligue 1",         "country": "France",      "odds_key": "soccer_france_ligue_one"},
    "PPL": {"name": "Primeira Liga",   "country": "Portugal",    "odds_key": "soccer_portugal_primeira_liga"},
    "DED": {"name": "Eredivisie",      "country": "Netherlands", "odds_key": "soccer_netherlands_eredivisie"},
    "BSA": {"name": "Brasileirão",     "country": "Brazil",      "odds_key": "soccer_brazil_campeonato"},
    "CL":  {"name": "Champions League","country": "Europe",      "odds_key": "soccer_uefa_champs_league"},
    "ELC": {"name": "Championship",    "country": "England",     "odds_key": "soccer_efl_champ"},
}

# Conjunto de códigos suportados (usado em main.py para filtrar)
SUPPORTED_LEAGUE_IDS = set(SUPPORTED_COMPETITIONS.keys())

# ── Rate limiter: football-data.org (10 req/min free tier) ────────────────
_fd_last_request = 0.0
_FD_MIN_INTERVAL = 6.5   # 6.5s entre chamadas ≈ 9.2 req/min (abaixo do limite)


def fd_api_get(path, params=None, timeout=15):
    """
    GET para football-data.org com rate limiting automático.
    Retry automático se receber 429 (rate limit temporário).
    """
    global _fd_last_request
    elapsed = time.time() - _fd_last_request
    if elapsed < _FD_MIN_INTERVAL:
        time.sleep(_FD_MIN_INTERVAL - elapsed)
    _fd_last_request = time.time()

    url = f"{FOOTBALLDATA_BASE_URL}{path}"
    r = requests.get(url, headers=FOOTBALLDATA_HEADERS, params=params, timeout=timeout)

    if r.status_code == 429:
        print("  [!] Rate limit atingido — a aguardar 60s...")
        time.sleep(60)
        return fd_api_get(path, params, timeout)

    r.raise_for_status()
    return r


def odds_api_get(path, params=None, timeout=15):
    """
    GET para The Odds API.
    Avisa automaticamente se os créditos mensais estiverem abaixo de 50.
    """
    if params is None:
        params = {}
    params["apiKey"] = ODDS_API_KEY

    url = f"{ODDS_API_BASE_URL}{path}"
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()

    remaining = r.headers.get("x-requests-remaining")
    if remaining is not None and int(remaining) < 50:
        print(f"  [!] AVISO: Odds API — apenas {remaining} créditos restantes este mês.")

    return r
