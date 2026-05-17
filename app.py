import os
import logging
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="TipFactory", version="12.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# === API-FOOTBALL V3 CONFIG ===
API_KEY = os.getenv("API_FOOTBALL_KEY", "247e8b9eb521d5081463f72ca03ca37b")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

CACHE = {}
REQUEST_COUNT = {"total": 0, "today": datetime.now().date(), "by_endpoint": {}}
RATE_LIMIT = {"remaining": None, "limit": None, "reset": None}

# === RATE LIMIT PROTECTION ===
DAILY_REQUEST_LIMIT = int(os.getenv("DAILY_API_LIMIT", "100"))
SAFE_REQUEST_BUFFER = 10

def can_make_api_request():
    today = datetime.now().date()
    if REQUEST_COUNT["today"] != today:
        REQUEST_COUNT["total"] = 0
        REQUEST_COUNT["by_endpoint"] = {}
        REQUEST_COUNT["today"] = today
    remaining = DAILY_REQUEST_LIMIT - REQUEST_COUNT["total"]
    if RATE_LIMIT.get("remaining"):
        try:
            api_remaining = int(RATE_LIMIT["remaining"])
            remaining = min(remaining, api_remaining)
        except:
            pass
    return remaining > SAFE_REQUEST_BUFFER

def get_requests_remaining():
    today = datetime.now().date()
    if REQUEST_COUNT["today"] != today:
        return DAILY_REQUEST_LIMIT
    return max(0, DAILY_REQUEST_LIMIT - REQUEST_COUNT["total"])



# === CACHE EN DISCO (para persistencia entre reinicios) ===
CACHE_DIR = "/tmp/tipfactory_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def disk_cache_path(key):
    return os.path.join(CACHE_DIR, f"{key}.json")

def save_to_disk(key, data):
    """Guarda cache en disco como JSON"""
    try:
        filepath = disk_cache_path(key)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "data": data,
                "saved_at": datetime.now(timezone.utc).isoformat()
            }, f, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving disk cache {key}: {e}")
        return False

def load_from_disk(key, max_age_hours=24):
    """Lee cache de disco si no ha expirado"""
    try:
        filepath = disk_cache_path(key)
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        saved = datetime.fromisoformat(cached["saved_at"])
        age_hours = (datetime.now(timezone.utc) - saved).total_seconds() / 3600
        if age_hours > max_age_hours:
            return None
        return cached["data"]
    except Exception as e:
        logger.error(f"Error loading disk cache {key}: {e}")
        return None

def delete_disk_cache(pattern=""):
    """Limpia archivos de cache antiguos"""
    try:
        for filename in os.listdir(CACHE_DIR):
            if pattern in filename:
                os.remove(os.path.join(CACHE_DIR, filename))
    except Exception as e:
        logger.error(f"Error cleaning disk cache: {e}")

# === LIGAS SOPORTADAS ===
LEAGUE_IDS = {
    "PL": 39, "PD": 140, "SA": 135, "BL1": 78, "FL1": 61,
    "ELC": 40, "SP": 141, "SI": 131, "SD": 81, "FL2": 62,
    "PPL": 94, "DED": 88, "BE": 144, "CH": 207, "DK": 119,
    "NO": 103, "FI": 244, "CZ": 346, "GR": 197, "TR": 203,
    "HR": 210, "RO": 283, "SC": 180, "PLN": 106, "AU": 218,
    "BSA": 71, "BRA_B": 72, "ARG": 128, "ARG_B": 129, "COL": 239,
    "CHI": 265, "URU": 268, "PAR": 252, "ECU": 242, "PER": 281,
    "MX": 262, "MX_B": 263, "MLS": 253, "USL": 255, "CAN": 259,
    "CRC": 163, "GT": 370, "HN": 300, "SV": 279, "PA": 287, "JM": 357,
    "JP": 98, "JP_B": 99, "KR": 292, "KR_B": 293, "CN": 169,
    "AU_A": 113, "SA_A": 307, "AE": 301, "QA": 340, "IR": 291,
    "EG": 233, "ZA": 289, "MA": 200, "TN": 194, "DZ": 186,
    "NG": 371, "GH": 376,
    "CL": 2, "EL": 3, "ECL": 848, "NATIONS": 5,
    "CLI": 13, "CSA": 11, "COPA": 9,
    "WC": 1, "EURO": 4, "AFCON": 6, "GOLD": 22, "ASIA": 7, "WCC": 10,
}

COMPETITIONS = {
    "PL": "Premier League", "PD": "La Liga", "SA": "Serie A",
    "BL1": "Bundesliga", "FL1": "Ligue 1",
    "ELC": "Championship", "SP": "La Liga 2", "SI": "Serie B",
    "SD": "2. Bundesliga", "FL2": "Ligue 2",
    "PPL": "Primeira Liga", "DED": "Eredivisie", "BE": "Jupiler Pro League",
    "CH": "Super League Suiza", "DK": "Superliga Dinamarca",
    "NO": "Eliteserien", "FI": "Veikkausliiga", "CZ": "First League Checa",
    "GR": "Super League Grecia", "TR": "Süper Lig", "HR": "HNL Croacia",
    "RO": "Liga I Rumanía", "SC": "Premiership Escocia",
    "PLN": "Ekstraklasa Polonia", "AU": "Bundesliga Austria",
    "BSA": "Brasileirao", "BRA_B": "Série B Brasil",
    "ARG": "Liga Argentina", "ARG_B": "Primera Nacional",
    "COL": "Liga Colombia", "CHI": "Primera División Chile",
    "URU": "Primera División Uruguay", "PAR": "Primera División Paraguay",
    "ECU": "Serie A Ecuador", "PER": "Liga 1 Perú",
    "MX": "Liga MX", "MX_B": "Liga Expansión MX",
    "MLS": "MLS", "USL": "USL Championship", "CAN": "Canadian Premier League",
    "CRC": "Primera División Costa Rica", "GT": "Liga Nacional Guatemala",
    "HN": "Liga Nacional Honduras", "SV": "Primera División El Salvador",
    "PA": "LPF Panamá", "JM": "Premier League Jamaica",
    "JP": "J1 League", "JP_B": "J2 League", "KR": "K League",
    "KR_B": "K League 2", "CN": "Super League China",
    "AU_A": "A-League", "SA_A": "Pro League Saudi",
    "AE": "UAE Pro League", "QA": "Stars League Qatar",
    "IR": "Persian Gulf Pro League",
    "EG": "Premier League Egypt", "ZA": "Premier Division RSA",
    "MA": "Botola Pro", "TN": "Ligue 1 Túnez", "DZ": "Ligue 1 Argelia",
    "NG": "NPFL Nigeria", "GH": "Premier League Ghana",
    "CL": "Champions League", "EL": "Europa League",
    "ECL": "Conference League", "NATIONS": "Nations League",
    "CLI": "Copa Libertadores", "CSA": "Copa Sudamericana",
    "COPA": "Copa América",
    "WC": "World Cup", "EURO": "Euro", "AFCON": "Africa Cup",
    "GOLD": "Gold Cup", "ASIA": "Asian Cup", "WCC": "FIFA Club World Cup",
}

DEFAULT_COMPETITIONS = [
    "PL", "PD", "SA", "BL1", "FL1", "ELC", "SP", "SI", "SD", "FL2",
    "PPL", "DED", "BE", "CH", "DK", "NO", "FI", "CZ", "GR", "TR",
    "HR", "RO", "SC", "PLN", "AU",
    "BSA", "BRA_B", "ARG", "ARG_B", "COL", "CHI", "URU", "PAR",
    "ECU", "PER", "MX", "MX_B", "MLS", "USL", "CAN",
    "CRC", "GT", "HN", "SV", "PA", "JM",
    "JP", "JP_B", "KR", "KR_B", "CN", "AU_A", "SA_A", "AE", "QA", "IR",
    "EG", "ZA", "MA", "TN", "DZ", "NG", "GH",
    "CL", "EL", "ECL", "NATIONS", "CLI", "CSA", "COPA",
    "WC", "EURO", "AFCON", "GOLD", "ASIA", "WCC",
]

MAX_WORKERS = 10

def cache_get(key, ttl=3600):
    if key in CACHE:
        data, ts = CACHE[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None

def cache_set(key, data):
    CACHE[key] = (data, datetime.now())

def track_request(endpoint):
    today = datetime.now().date()
    if REQUEST_COUNT["today"] != today:
        REQUEST_COUNT["total"] = 0
        REQUEST_COUNT["by_endpoint"] = {}
        REQUEST_COUNT["today"] = today
    REQUEST_COUNT["total"] += 1
    REQUEST_COUNT["by_endpoint"][endpoint] = REQUEST_COUNT["by_endpoint"].get(endpoint, 0) + 1

def api_get(endpoint, params=None, cache_key=None, ttl=3600, force=False):
    if cache_key:
        cached = cache_get(cache_key, ttl)
        if cached is not None:
            return cached

    if not force and not can_make_api_request():
        logger.warning(f"RATE LIMIT: skipping {endpoint} (remaining: {get_requests_remaining()})")
        return None

    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}/"
        track_request(endpoint)
        logger.info(f"API CALL #{REQUEST_COUNT['total']}/{DAILY_REQUEST_LIMIT}: {url} | params={params}")
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)

        RATE_LIMIT["remaining"] = resp.headers.get("x-ratelimit-requests-remaining")
        RATE_LIMIT["limit"] = resp.headers.get("x-ratelimit-requests-limit")
        RATE_LIMIT["reset"] = resp.headers.get("x-ratelimit-reset")

        if resp.status_code == 429:
            logger.warning(f"RATE LIMIT API-Football! Remaining: {RATE_LIMIT.get('remaining')}")
            return None
        if resp.status_code in (401, 403):
            logger.error(f"AUTH ERROR {resp.status_code}: {resp.text[:200]}")
            return None

        resp.raise_for_status()
        data = resp.json()

        if data.get("errors"):
            logger.error(f"API-Football errors: {data['errors']}")
            return None

        if cache_key:
            cache_set(cache_key, data)

        return data
    except Exception as e:
        logger.error(f"API error: {e}")
        return None

def safe_get(d, *keys, default=None):
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default

def parse_score_value(v):
    if v == "" or v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None

def get_league_id(competition_code):
    return LEAGUE_IDS.get(competition_code)

def get_season():
    now = datetime.now(timezone.utc)
    if now.month >= 7:
        return now.year
    else:
        return now.year - 1

# ============================================================
# CACHE INTELIGENTE PARA FIXTURES Y STATS
# ============================================================

def get_cached_fixtures(date_str):
    """Lee fixtures de RAM o disco"""
    # 1. Intentar RAM
    ram_key = f"fixtures_{date_str}"
    ram_cached = cache_get(ram_key, ttl=43200)  # 12h en RAM
    if ram_cached:
        return ram_cached
    
    # 2. Intentar disco
    disk_cached = load_from_disk(ram_key, max_age_hours=12)
    if disk_cached:
        # Guardar en RAM para próximas lecturas
        cache_set(ram_key, disk_cached)
        return disk_cached
    
    return None

def save_cached_fixtures(date_str, data):
    """Guarda fixtures en RAM y disco"""
    ram_key = f"fixtures_{date_str}"
    cache_set(ram_key, data)
    save_to_disk(ram_key, data)

def get_cached_team_stats(team_id, league_id, season):
    """Lee stats de equipo de RAM o disco"""
    ram_key = f"team_stats_{team_id}_{league_id}_{season}"
    ram_cached = cache_get(ram_key, ttl=86400)  # 24h en RAM
    if ram_cached:
        return ram_cached
    
    disk_cached = load_from_disk(ram_key, max_age_hours=24)
    if disk_cached:
        cache_set(ram_key, disk_cached)
        return disk_cached
    
    return None

def save_cached_team_stats(team_id, league_id, season, data):
    """Guarda stats de equipo en RAM y disco"""
    ram_key = f"team_stats_{team_id}_{league_id}_{season}"
    cache_set(ram_key, data)
    save_to_disk(ram_key, data)

def get_cached_prediction(fixture_id):
    """Lee predicción de RAM o disco"""
    ram_key = f"prediction_{fixture_id}"
    ram_cached = cache_get(ram_key, ttl=21600)  # 6h en RAM
    if ram_cached:
        return ram_cached
    
    disk_cached = load_from_disk(ram_key, max_age_hours=6)
    if disk_cached:
        cache_set(ram_key, disk_cached)
        return disk_cached
    
    return None

def save_cached_prediction(fixture_id, data):
    """Guarda predicción en RAM y disco"""
    ram_key = f"prediction_{fixture_id}"
    cache_set(ram_key, data)
    save_to_disk(ram_key, data)

def get_cached_match_stats(fixture_id):
    """Lee stats de partido de RAM o disco"""
    ram_key = f"match_stats_{fixture_id}"
    ram_cached = cache_get(ram_key, ttl=86400)
    if ram_cached:
        return ram_cached
    
    disk_cached = load_from_disk(ram_key, max_age_hours=24)
    if disk_cached:
        cache_set(ram_key, disk_cached)
        return disk_cached
    
    return None

def save_cached_match_stats(fixture_id, data):
    """Guarda stats de partido en RAM y disco"""
    ram_key = f"match_stats_{fixture_id}"
    cache_set(ram_key, data)
    save_to_disk(ram_key, data)

def get_cached_events(fixture_id):
    """Lee eventos de RAM o disco"""
    ram_key = f"events_{fixture_id}"
    ram_cached = cache_get(ram_key, ttl=86400)
    if ram_cached:
        return ram_cached
    
    disk_cached = load_from_disk(ram_key, max_age_hours=24)
    if disk_cached:
        cache_set(ram_key, disk_cached)
        return disk_cached
    
    return None

def save_cached_events(fixture_id, data):
    """Guarda eventos en RAM y disco"""
    ram_key = f"events_{fixture_id}"
    cache_set(ram_key, data)
    save_to_disk(ram_key, data)

# ============================================================
# ESTADÍSTICAS DE PARTIDO
# ============================================================

def get_fixture_statistics(fixture_id):
    if not fixture_id:
        return {}

    # INTENTAR CACHE PRIMERO
    cached = get_cached_match_stats(fixture_id)
    if cached is not None:
        return cached

    data = api_get(
        "fixtures/statistics",
        params={"fixture": fixture_id},
        cache_key=f"fixture_stats_{fixture_id}",
        ttl=86400
    )

    if not data or not isinstance(data, dict):
        return {}

    result = {}
    for item in data.get("response", []):
        team_id = safe_get(item, "team", "id")
        stats_list = item.get("statistics", [])
        parsed = {}
        for stat in stats_list:
            stat_type = stat.get("type", "").strip()
            value = stat.get("value")
            parsed[stat_type] = value
        if team_id:
            result[team_id] = parsed
    
    # GUARDAR EN CACHE
    save_cached_match_stats(fixture_id, result)
    return result

def get_fixture_events(fixture_id):
    if not fixture_id:
        return []

    # INTENTAR CACHE PRIMERO
    cached = get_cached_events(fixture_id)
    if cached is not None:
        return cached

    data = api_get(
        "fixtures/events",
        params={"fixture": fixture_id},
        cache_key=f"fixture_events_{fixture_id}",
        ttl=86400
    )

    if not data or not isinstance(data, dict):
        return []
    
    events = data.get("response", [])
    save_cached_events(fixture_id, events)
    return events

# ============================================================
# ESTADÍSTICAS REALES DEL EQUIPO
# ============================================================

def get_team_real_stats(team_id, league_id, season, max_fixtures=10):
    if not team_id or not league_id or not season:
        return None

    # INTENTAR CACHE PRIMERO
    cached = get_cached_team_stats(team_id, league_id, season)
    if cached:
        logger.info(f"Team {team_id}: CACHE HIT")
        return cached

    fixtures_data = api_get(
        "fixtures",
        params={
            "team": team_id,
            "league": league_id,
            "season": season,
            "last": max_fixtures,
            "status": "ft"
        },
        cache_key=f"team_fixtures_ft_{team_id}_{league_id}_{season}_{max_fixtures}",
        ttl=14400
    )

    if not fixtures_data or not isinstance(fixtures_data, dict):
        return None

    fixtures = fixtures_data.get("response", [])
    if not fixtures:
        return None

    total_gf = 0; total_ga = 0
    total_corners = 0; total_corners_conceded = 0
    total_yellow = 0; total_red = 0
    total_shots = 0; total_shots_on = 0
    total_possession = 0; total_fouls = 0
    total_offsides = 0; total_passes = 0; total_passes_acc = 0

    matches_with_stats = 0
    matches_with_goals = 0
    matches_with_corners = 0
    matches_with_cards = 0

    over_15_count = 0; over_25_count = 0; over_35_count = 0
    btts_count = 0; clean_sheet_count = 0; failed_score_count = 0

    corners_over_45 = 0; corners_over_55 = 0; corners_over_65 = 0
    corners_over_75 = 0; corners_over_85 = 0; corners_over_95 = 0
    corners_over_105 = 0

    cards_over_15 = 0; cards_over_25 = 0; cards_over_35 = 0
    cards_over_45 = 0; cards_over_55 = 0; cards_over_65 = 0

    shots_over_95 = 0; shots_over_115 = 0; shots_over_135 = 0

    # === PARALELIZAR: Obtener stats de todos los partidos ===
    def fetch_fixture_data(fixture):
        fixture_id = safe_get(fixture, "fixture", "id")
        if not fixture_id:
            return None
        
        stats = get_fixture_statistics(fixture_id)
        events = get_fixture_events(fixture_id)
        return {
            "fixture_id": fixture_id,
            "fixture": fixture,
            "stats": stats,
            "events": events
        }

    fixture_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_fixture_data, f) for f in fixtures]
        for future in as_completed(futures):
            result = future.result()
            if result:
                fixture_results.append(result)

    fixture_results.sort(
        key=lambda x: x["fixture"].get("fixture", {}).get("date", ""),
        reverse=True
    )

    for result in fixture_results:
        fixture = result["fixture"]
        fixture_stats = result["stats"]
        fixture_events = result["events"]
        fixture_id = result["fixture_id"]

        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})

        home_team = teams.get("home", {})
        away_team = teams.get("away", {})
        is_home = home_team.get("id") == team_id
        opponent_id = away_team.get("id") if is_home else home_team.get("id")

        home_goals = goals.get("home", 0) or 0
        away_goals = goals.get("away", 0) or 0

        if is_home:
            gf = home_goals; ga = away_goals
        else:
            gf = away_goals; ga = home_goals

        total_goals = gf + ga
        total_gf += gf; total_ga += ga
        matches_with_goals += 1

        if total_goals > 1.5: over_15_count += 1
        if total_goals > 2.5: over_25_count += 1
        if total_goals > 3.5: over_35_count += 1
        if gf > 0 and ga > 0: btts_count += 1
        if ga == 0: clean_sheet_count += 1
        if gf == 0: failed_score_count += 1

        team_stats = fixture_stats.get(team_id, {}) if fixture_stats else {}
        opponent_stats = fixture_stats.get(opponent_id, {}) if fixture_stats and opponent_id else {}

        has_stats = False
        match_corners = None
        match_corners_opp = None
        match_yellow = None; match_red = None
        match_shots = None

        if team_stats:
            corners = team_stats.get("Corner Kicks")
            if corners is not None:
                try:
                    match_corners = int(corners)
                    total_corners += match_corners
                    has_stats = True
                except: pass

            if opponent_stats:
                opp_corners = opponent_stats.get("Corner Kicks")
                if opp_corners is not None:
                    try:
                        match_corners_opp = int(opp_corners)
                        total_corners_conceded += match_corners_opp
                    except: pass

            yellow = team_stats.get("Yellow Cards")
            if yellow is not None:
                try:
                    match_yellow = int(yellow)
                    total_yellow += match_yellow
                    has_stats = True
                except: pass

            red = team_stats.get("Red Cards")
            if red is not None:
                try:
                    match_red = int(red)
                    total_red += match_red
                    has_stats = True
                except: pass

            shots = team_stats.get("Total Shots")
            if shots is not None:
                try:
                    match_shots = int(shots)
                    total_shots += match_shots
                    has_stats = True
                except: pass

            shots_on = team_stats.get("Shots on Goal")
            if shots_on is not None:
                try:
                    total_shots_on += int(shots_on)
                    has_stats = True
                except: pass

            possession = team_stats.get("Ball Possession")
            if possession is not None:
                try:
                    if isinstance(possession, str):
                        possession = int(possession.replace("%", "").strip())
                    total_possession += int(possession)
                    has_stats = True
                except: pass

            fouls = team_stats.get("Fouls")
            if fouls is not None:
                try:
                    total_fouls += int(fouls)
                    has_stats = True
                except: pass

            offsides = team_stats.get("Offsides")
            if offsides is not None:
                try:
                    total_offsides += int(offsides)
                    has_stats = True
                except: pass

        if match_yellow is None or match_red is None:
            if fixture_events:
                yellow_count = sum(1 for e in fixture_events
                    if e.get("team", {}).get("id") == team_id
                    and e.get("type") == "Card"
                    and e.get("detail") == "Yellow Card")
                red_count = sum(1 for e in fixture_events
                    if e.get("team", {}).get("id") == team_id
                    and e.get("type") == "Card"
                    and e.get("detail") == "Red Card")

                if match_yellow is None:
                    match_yellow = yellow_count
                    total_yellow += match_yellow
                if match_red is None:
                    match_red = red_count
                    total_red += match_red
                has_stats = True

        if match_corners is not None:
            matches_with_corners += 1
            if match_corners > 4.5: corners_over_45 += 1
            if match_corners > 5.5: corners_over_55 += 1
            if match_corners > 6.5: corners_over_65 += 1
            if match_corners > 7.5: corners_over_75 += 1
            if match_corners > 8.5: corners_over_85 += 1
            if match_corners > 9.5: corners_over_95 += 1
            if match_corners > 10.5: corners_over_105 += 1

        if match_yellow is not None and match_red is not None:
            total_cards = match_yellow + match_red
            matches_with_cards += 1
            if total_cards > 1.5: cards_over_15 += 1
            if total_cards > 2.5: cards_over_25 += 1
            if total_cards > 3.5: cards_over_35 += 1
            if total_cards > 4.5: cards_over_45 += 1
            if total_cards > 5.5: cards_over_55 += 1
            if total_cards > 6.5: cards_over_65 += 1

        if match_shots is not None:
            if match_shots > 9.5: shots_over_95 += 1
            if match_shots > 11.5: shots_over_115 += 1
            if match_shots > 13.5: shots_over_135 += 1

        if has_stats:
            matches_with_stats += 1

    played = matches_with_goals
    if played == 0:
        return None

    avg_gf = round(total_gf / played, 2)
    avg_ga = round(total_ga / played, 2)
    avg_total = round((total_gf + total_ga) / played, 2)

    avg_corners = round(total_corners / matches_with_corners, 2) if matches_with_corners else 0
    avg_corners_conceded = round(total_corners_conceded / matches_with_corners, 2) if matches_with_corners else 0
    avg_yellow = round(total_yellow / matches_with_stats, 2) if matches_with_stats else 0
    avg_red = round(total_red / matches_with_stats, 2) if matches_with_stats else 0
    avg_total_cards = round(avg_yellow + avg_red, 2)
    avg_shots = round(total_shots / matches_with_stats, 2) if matches_with_stats else 0
    avg_shots_on = round(total_shots_on / matches_with_stats, 2) if matches_with_stats else 0
    avg_possession = round(total_possession / matches_with_stats, 2) if matches_with_stats else 0
    avg_fouls = round(total_fouls / matches_with_stats, 2) if matches_with_stats else 0
    avg_offsides = round(total_offsides / matches_with_stats, 2) if matches_with_stats else 0

    over_15_pct = round((over_15_count / played) * 100, 1)
    over_25_pct = round((over_25_count / played) * 100, 1)
    over_35_pct = round((over_35_count / played) * 100, 1)
    btts_pct = round((btts_count / played) * 100, 1)
    clean_sheet_pct = round((clean_sheet_count / played) * 100, 1)
    failed_score_pct = round((failed_score_count / played) * 100, 1)

    corners_pct = {
        "over_4_5": round((corners_over_45 / matches_with_corners) * 100, 1) if matches_with_corners else 0,
        "over_5_5": round((corners_over_55 / matches_with_corners) * 100, 1) if matches_with_corners else 0,
        "over_6_5": round((corners_over_65 / matches_with_corners) * 100, 1) if matches_with_corners else 0,
        "over_7_5": round((corners_over_75 / matches_with_corners) * 100, 1) if matches_with_corners else 0,
        "over_8_5": round((corners_over_85 / matches_with_corners) * 100, 1) if matches_with_corners else 0,
        "over_9_5": round((corners_over_95 / matches_with_corners) * 100, 1) if matches_with_corners else 0,
        "over_10_5": round((corners_over_105 / matches_with_corners) * 100, 1) if matches_with_corners else 0,
        "matches": matches_with_corners,
    }

    cards_pct = {
        "over_1_5": round((cards_over_15 / matches_with_cards) * 100, 1) if matches_with_cards else 0,
        "over_2_5": round((cards_over_25 / matches_with_cards) * 100, 1) if matches_with_cards else 0,
        "over_3_5": round((cards_over_35 / matches_with_cards) * 100, 1) if matches_with_cards else 0,
        "over_4_5": round((cards_over_45 / matches_with_cards) * 100, 1) if matches_with_cards else 0,
        "over_5_5": round((cards_over_55 / matches_with_cards) * 100, 1) if matches_with_cards else 0,
        "over_6_5": round((cards_over_65 / matches_with_cards) * 100, 1) if matches_with_cards else 0,
        "matches": matches_with_cards,
    }

    shots_pct = {
        "over_9_5": round((shots_over_95 / matches_with_stats) * 100, 1) if matches_with_stats else 0,
        "over_11_5": round((shots_over_115 / matches_with_stats) * 100, 1) if matches_with_stats else 0,
        "over_13_5": round((shots_over_135 / matches_with_stats) * 100, 1) if matches_with_stats else 0,
        "matches": matches_with_stats,
    }

    result = {
        "played": played,
        "goals_for": total_gf,
        "goals_against": total_ga,
        "avg_team_goals": avg_gf,
        "avg_conceded": avg_ga,
        "avg_total_goals": avg_total,
        "avg_corners": avg_corners,
        "avg_corners_conceded": avg_corners_conceded,
        "avg_yellow_cards": avg_yellow,
        "avg_red_cards": avg_red,
        "avg_total_cards": avg_total_cards,
        "avg_shots": avg_shots,
        "avg_shots_on": avg_shots_on,
        "avg_possession": avg_possession,
        "avg_fouls": avg_fouls,
        "avg_offsides": avg_offsides,
        "over_1_5_pct": over_15_pct,
        "over_2_5_pct": over_25_pct,
        "over_3_5_pct": over_35_pct,
        "btts_pct": btts_pct,
        "clean_sheet_pct": clean_sheet_pct,
        "failed_to_score_pct": failed_score_pct,
        "matches_with_stats": matches_with_stats,
        "corners_pct": corners_pct,
        "cards_pct": cards_pct,
        "shots_pct": shots_pct,
    }
    
    # GUARDAR EN CACHE (RAM + DISCO)
    save_cached_team_stats(team_id, league_id, season, result)
    logger.info(f"Team {team_id}: calculated and cached")
    
    return result

# ============================================================
# PREDICCIONES
# ============================================================

def get_predictions(fixture_id):
    if not fixture_id:
        return None

    # INTENTAR CACHE PRIMERO
    cached = get_cached_prediction(fixture_id)
    if cached:
        return cached

    data = api_get(
        "predictions",
        params={"fixture": fixture_id},
        cache_key=f"predictions_{fixture_id}",
        ttl=3600
    )

    if not data or not isinstance(data, dict):
        return None

    response = data.get("response", [])
    if not response:
        return None

    pred = response[0] if isinstance(response, list) else response
    predictions = pred.get("predictions", {})
    comparison = pred.get("comparison", {})

    result = {
        "winner": predictions.get("winner", {}).get("name", ""),
        "winner_comment": predictions.get("winner", {}).get("comment", ""),
        "under_over": predictions.get("under_over", ""),
        "advice": predictions.get("advice", ""),
        "percent_home": safe_get(comparison, "home", default=""),
        "percent_draw": safe_get(comparison, "draw", default=""),
        "percent_away": safe_get(comparison, "away", default="")
    }
    
    save_cached_prediction(fixture_id, result)
    return result

# ============================================================
# FIXTURES POR FECHA
# ============================================================

def get_fixtures_by_date(date, league_id=None, season=None):
    params = {"date": date}
    if league_id:
        params["league"] = league_id
    if season:
        params["season"] = season

    data = api_get(
        "fixtures",
        params=params,
        cache_key=f"fixtures_{date}_{league_id or 'all'}",
        ttl=7200
    )

    if not data or not isinstance(data, dict):
        return []
    return data.get("response", [])

def format_fixture(f):
    fixture = f.get("fixture", {})
    teams = f.get("teams", {})
    goals = f.get("goals", {})
    league = f.get("league", {})

    home = teams.get("home", {})
    away = teams.get("away", {})

    status = fixture.get("status", {}).get("short", "NS")
    status_map = {
        "NS": "NS", "1H": "1H", "HT": "HT", "2H": "2H",
        "ET": "ET", "P": "PEN", "FT": "FT", "AET": "AET",
        "PEN": "PEN", "SUSP": "SUSP", "INT": "INT",
        "PST": "PST", "CANC": "CANC", "ABD": "ABD",
        "AWD": "AWD", "WO": "WO"
    }

    raw_matchday = league.get("round", "")
    matchday = 0
    if isinstance(raw_matchday, int):
        matchday = raw_matchday
    elif isinstance(raw_matchday, str):
        parts = raw_matchday.split("-")
        if parts:
            try:
                matchday = int(parts[-1].strip())
            except:
                matchday = 0

    return {
        "id": fixture.get("id"),
        "utcDate": fixture.get("date"),
        "matchDate": (fixture.get("date") or "")[:10],
        "status": status_map.get(status, status),
        "statusText": status,
        "minute": fixture.get("status", {}).get("elapsed", 0),
        "venue": fixture.get("venue", {}).get("name", ""),
        "matchday": matchday,
        "homeTeam": {
            "id": home.get("id"),
            "name": home.get("name", "Local"),
            "shortName": home.get("name", "Local")[:15],
            "crest": home.get("logo", "")
        },
        "awayTeam": {
            "id": away.get("id"),
            "name": away.get("name", "Visitante"),
            "shortName": away.get("name", "Visitante")[:15],
            "crest": away.get("logo", "")
        },
        "competition": {
            "id": league.get("id"),
            "name": league.get("name", ""),
            "code": ""
        },
        "league_name": league.get("name", ""),
        "country": league.get("country", ""),
        "homeScore": goals.get("home"),
        "awayScore": goals.get("away"),
        "api_football_fixture_id": fixture.get("id")
    }

# ============================================================
# PRECARGA DIARIA (se ejecuta al iniciar y via cron)
# ============================================================

def precache_daily_data():
    """Precarga fixtures y stats para los próximos días"""
    logger.info("=" * 60)
    logger.info("INICIANDO PRECARGA DIARIA")
    logger.info("=" * 60)
    
    season = get_season()
    today = datetime.now(timezone.utc).date()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
    
    # 1. Precargar fixtures
    for date_str in dates:
        logger.info(f"Precaching fixtures for {date_str}...")
        all_matches = []
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_code = {}
            for code in DEFAULT_COMPETITIONS:
                league_id = get_league_id(code)
                if league_id:
                    future = executor.submit(get_fixtures_by_date, date_str, league_id, season)
                    future_to_code[future] = code
            
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    fixtures = future.result(timeout=30)
                    if fixtures:
                        all_matches.extend([format_fixture(f) for f in fixtures])
                except Exception as e:
                    logger.error(f"Error precaching {code}: {e}")
        
        seen = set()
        unique = []
        for m in all_matches:
            if m["id"] not in seen:
                seen.add(m["id"])
                unique.append(m)
        unique.sort(key=lambda x: x.get("utcDate", ""))
        
        save_cached_fixtures(date_str, {
            "matches": unique,
            "competitions_found": [{"code": c, "name": COMPETITIONS.get(c, c)} for c in set(m.get("competition", {}).get("id", "") for m in unique)],
            "date": date_str
        })
        logger.info(f"Saved {len(unique)} fixtures for {date_str}")
    
    # 2. Precargar stats para ligas top
    top_leagues = ["PL", "PD", "SA", "BL1", "FL1", "CL", "BSA", "ARG", "MLS", "MX"]
    
    for code in top_leagues:
        league_id = get_league_id(code)
        if not league_id:
            continue
        
        logger.info(f"Precaching team stats for {code}...")
        
        fixtures_data = api_get(
            "fixtures",
            params={"league": league_id, "season": season, "last": 10, "status": "ft"},
            cache_key=f"precache_teams_{code}_{season}",
            ttl=86400
        )
        
        if not fixtures_data:
            continue
        
        team_ids = set()
        for f in fixtures_data.get("response", []):
            teams = f.get("teams", {})
            if teams.get("home", {}).get("id"):
                team_ids.add(teams["home"]["id"])
            if teams.get("away", {}).get("id"):
                team_ids.add(teams["away"]["id"])
        
        for team_id in team_ids:
            try:
                stats = get_team_real_stats(team_id, league_id, season, max_fixtures=10)
                if stats:
                    logger.info(f"Cached team {team_id}")
            except Exception as e:
                logger.error(f"Error precaching team {team_id}: {e}")
        
        logger.info(f"Precached {len(team_ids)} teams for {code}")
    
    logger.info("=" * 60)
    logger.info("PRECARGA DIARIA COMPLETADA")
    logger.info("=" * 60)

# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/matches")
def api_matches(date: str = Query(None)):
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # 1. INTENTAR LEER DE CACHE (RAM o DISCO)
    cached = get_cached_fixtures(date)
    if cached:
        return {
            "matches": cached.get("matches", []),
            "requested_date": date,
            "source_date": date,
            "is_exact": True,
            "competitions_found": cached.get("competitions_found", []),
            "source": "api-football.com (cached)",
            "requests_today": REQUEST_COUNT["total"],
            "rate_limit_remaining": RATE_LIMIT.get("remaining"),
            "cached": True
        }
    
    # 2. FALLBACK: LLAMAR API EN PARALELO
    season = get_season()
    collected = []
    found = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_code = {}
        for code in DEFAULT_COMPETITIONS:
            league_id = get_league_id(code)
            if league_id:
                future = executor.submit(get_fixtures_by_date, date, league_id, season)
                future_to_code[future] = code
        
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try:
                fixtures = future.result(timeout=30)
                if fixtures:
                    comp_matches = [format_fixture(f) for f in fixtures]
                    if comp_matches:
                        collected.extend(comp_matches)
                        found.append({"code": code, "name": COMPETITIONS.get(code, code)})
            except Exception as e:
                logger.error(f"Error fetching {code}: {e}")
    
    seen = set()
    unique = []
    for m in collected:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)
    unique.sort(key=lambda x: x.get("utcDate", ""))
    
    # Guardar en cache
    if unique:
        save_cached_fixtures(date, {
            "matches": unique,
            "competitions_found": found,
            "date": date
        })
    
    return {
        "matches": unique,
        "requested_date": date,
        "source_date": date if unique else None,
        "is_exact": True,
        "competitions_found": found,
        "source": "api-football.com (live)",
        "requests_today": REQUEST_COUNT["total"],
        "rate_limit_remaining": RATE_LIMIT.get("remaining"),
        "cached": False
    }

@app.get("/api/analyze/{match_id}")
def analyze(
    match_id: int,
    home_id: int = Query(...),
    away_id: int = Query(...),
    competition_id: int = Query(...),
    home_team: str = Query("Local"),
    away_team: str = Query("Visitante"),
    home_short: str = Query("Local"),
    away_short: str = Query("Visitante"),
    home_logo: str = Query(""),
    away_logo: str = Query(""),
    league: str = Query(""),
    country: str = Query(""),
    date: str = Query(""),
    time: str = Query("--:--"),
    venue: str = Query(""),
    home_score: str = Query(""),
    away_score: str = Query(""),
    matchday: str = Query("0"),
    status: str = Query("SCHEDULED")
):
    logger.info(f"=== ANALYZE match_id={match_id}, home={home_team}({home_id}), away={away_team}({away_id}) ===")

    comp_code = None
    for code, name in COMPETITIONS.items():
        if name.lower() in (league or "").lower():
            comp_code = code
            break
    if not comp_code:
        for code, lid in LEAGUE_IDS.items():
            if lid == competition_id:
                comp_code = code
                break

    league_id = get_league_id(comp_code) if comp_code else competition_id
    season = get_season()

    # === INTENTAR LEER DE CACHE PRIMERO ===
    home_cached = get_cached_team_stats(home_id, league_id, season)
    away_cached = get_cached_team_stats(away_id, league_id, season)
    
    home_stats = home_cached if home_cached else None
    away_stats = away_cached if away_cached else None
    home_form_data = None
    away_form_data = None
    
    home_mode = "CACHED" if home_stats else "LIVE"
    away_mode = "CACHED" if away_stats else "LIVE"
    
    # Si no hay cache, obtener en tiempo real (PARALELO)
    if not home_stats or not away_stats:
        def fetch_home():
            return get_team_real_stats(home_id, league_id, season, max_fixtures=10) if league_id else None
        def fetch_away():
            return get_team_real_stats(away_id, league_id, season, max_fixtures=10) if league_id else None
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            home_future = executor.submit(fetch_home)
            away_future = executor.submit(fetch_away)
            
            if not home_stats:
                home_stats = home_future.result(timeout=60)
                home_mode = "LIVE"
            if not away_stats:
                away_stats = away_future.result(timeout=60)
                away_mode = "LIVE"
    
    # Obtener forma
    if not home_form_data:
        home_form_data = api_get(
            "teams/statistics",
            params={"team": home_id, "league": league_id, "season": season},
            cache_key=f"team_stats_form_{home_id}_{league_id}_{season}",
            ttl=28800
        )
    if not away_form_data:
        away_form_data = api_get(
            "teams/statistics",
            params={"team": away_id, "league": league_id, "season": season},
            cache_key=f"team_stats_form_{away_id}_{league_id}_{season}",
            ttl=28800
        )

    def parse_form(form_data):
        if not form_data or not isinstance(form_data, dict):
            return [], ""
        response = form_data.get("response", {})
        form_str = response.get("form", "") if isinstance(response, dict) else ""
        form_list = []
        for char in (form_str or "")[-5:]:
            if char == "W":
                form_list.append({"result": "W", "result_text": "Victoria"})
            elif char == "D":
                form_list.append({"result": "D", "result_text": "Empate"})
            elif char == "L":
                form_list.append({"result": "L", "result_text": "Derrota"})
        return form_list, form_str or ""

    home_form, home_form_str = parse_form(home_form_data)
    away_form, away_form_str = parse_form(away_form_data)

    # FALLBACK mejorado
    if not home_stats or home_stats["played"] == 0:
        home_stats = {
            "played": 0, "goals_for": 0, "goals_against": 0,
            "avg_team_goals": 1.25, "avg_conceded": 1.25, "avg_total_goals": 2.5,
            "avg_corners": 4.5, "avg_corners_conceded": 4.5,
            "avg_yellow_cards": 2.0, "avg_red_cards": 0.15,
            "avg_total_cards": 2.15, "avg_shots": 10, "avg_shots_on": 4,
            "avg_possession": 50, "avg_fouls": 12, "avg_offsides": 2,
            "over_1_5_pct": 70, "over_2_5_pct": 50, "over_3_5_pct": 25,
            "btts_pct": 50, "clean_sheet_pct": 20, "failed_to_score_pct": 20,
            "matches_with_stats": 0,
            "corners_pct": {
                "over_4_5": 0, "over_5_5": 0, "over_6_5": 0, "over_7_5": 0,
                "over_8_5": 0, "over_9_5": 0, "over_10_5": 0, "matches": 0
            },
            "cards_pct": {
                "over_1_5": 0, "over_2_5": 0, "over_3_5": 0, "over_4_5": 0,
                "over_5_5": 0, "over_6_5": 0, "matches": 0
            },
            "shots_pct": {
                "over_9_5": 0, "over_11_5": 0, "over_13_5": 0, "matches": 0
            },
        }
        home_mode = "DEFAULT"

    if not away_stats or away_stats["played"] == 0:
        away_stats = {
            "played": 0, "goals_for": 0, "goals_against": 0,
            "avg_team_goals": 1.25, "avg_conceded": 1.25, "avg_total_goals": 2.5,
            "avg_corners": 4.5, "avg_corners_conceded": 4.5,
            "avg_yellow_cards": 2.0, "avg_red_cards": 0.15,
            "avg_total_cards": 2.15, "avg_shots": 10, "avg_shots_on": 4,
            "avg_possession": 50, "avg_fouls": 12, "avg_offsides": 2,
            "over_1_5_pct": 70, "over_2_5_pct": 50, "over_3_5_pct": 25,
            "btts_pct": 50, "clean_sheet_pct": 20, "failed_to_score_pct": 20,
            "matches_with_stats": 0,
            "corners_pct": {
                "over_4_5": 0, "over_5_5": 0, "over_6_5": 0, "over_7_5": 0,
                "over_8_5": 0, "over_9_5": 0, "over_10_5": 0, "matches": 0
            },
            "cards_pct": {
                "over_1_5": 0, "over_2_5": 0, "over_3_5": 0, "over_4_5": 0,
                "over_5_5": 0, "over_6_5": 0, "matches": 0
            },
            "shots_pct": {
                "over_9_5": 0, "over_11_5": 0, "over_13_5": 0, "matches": 0
            },
        }
        away_mode = "DEFAULT"

    # PREDICCIONES: INTENTAR CACHE PRIMERO
    predictions = get_cached_prediction(match_id)
    pred_mode = "CACHED" if predictions else "LIVE"
    
    if not predictions:
        predictions = get_predictions(match_id)

    probabilities = {
        "over_1_5": round((home_stats["over_1_5_pct"] + away_stats["over_1_5_pct"]) / 2, 1),
        "over_2_5": round((home_stats["over_2_5_pct"] + away_stats["over_2_5_pct"]) / 2, 1),
        "over_3_5": round((home_stats["over_3_5_pct"] + away_stats["over_3_5_pct"]) / 2, 1),
        "btts": round((home_stats["btts_pct"] + away_stats["btts_pct"]) / 2, 1),
        "total_expected_goals": round(home_stats["avg_team_goals"] + away_stats["avg_team_goals"], 2),
        "home_xg": 0,
        "away_xg": 0
    }

    odds = {"home": 0, "draw": 0, "away": 0}
    if predictions:
        try:
            odds["home"] = float(str(predictions.get("percent_home", "0")).replace("%", "")) / 100 if predictions.get("percent_home") else 0
            odds["draw"] = float(str(predictions.get("percent_draw", "0")).replace("%", "")) / 100 if predictions.get("percent_draw") else 0
            odds["away"] = float(str(predictions.get("percent_away", "0")).replace("%", "")) / 100 if predictions.get("percent_away") else 0
        except:
            pass

    return JSONResponse({
        "match_info": {
            "home_team": home_team,
            "away_team": away_team,
            "home_short": home_short,
            "away_short": away_short,
            "home_logo": home_logo,
            "away_logo": away_logo,
            "league": league,
            "country": country,
            "date": date,
            "time": time,
            "venue": venue,
            "status": status,
            "matchday": matchday,
            "home_score": parse_score_value(home_score),
            "away_score": parse_score_value(away_score)
        },
        "home_form": home_form,
        "away_form": away_form,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "predictions": predictions,
        "probabilities": probabilities,
        "odds": odds,
        "stats_available": bool(home_stats["played"] or away_stats["played"]),
        "requests_today": REQUEST_COUNT["total"],
        "rate_limit_remaining": RATE_LIMIT.get("remaining"),
        "debug": {
            "match_id": match_id,
            "home_id": home_id,
            "away_id": away_id,
            "competition_id": competition_id,
            "league_id_api_football": league_id,
            "comp_code": comp_code,
            "season": season,
            "home_mode_used": home_mode,
            "away_mode_used": away_mode,
            "pred_mode": pred_mode,
            "home_stats_played": home_stats["played"],
            "away_stats_played": away_stats["played"]
        }
    })

@app.get("/api/precache")
def trigger_precache():
    """Endpoint manual para disparar precarga (para testing)"""
    def run_in_background():
        precache_daily_data()
    
    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()
    
    return {
        "status": "precache_started",
        "message": "La precarga se está ejecutando en background. Puede tardar 2-5 minutos.",
        "time": datetime.now().isoformat()
    }

@app.get("/ping")
def ping():
    return {"status": "ok", "time": datetime.now().isoformat()}

@app.get("/health")
def health():
    # Contar archivos de cache en disco
    cache_files = 0
    try:
        cache_files = len(os.listdir(CACHE_DIR))
    except:
        pass
    
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "cache_ram_size": len(CACHE),
        "cache_disk_files": cache_files,
        "cache_dir": CACHE_DIR,
        "api_football": "configured",
        "version": "12.0.0",
        "requests_today": REQUEST_COUNT["total"],
        "rate_limit_remaining": RATE_LIMIT.get("remaining"),
        "rate_limit_total": RATE_LIMIT.get("limit")
    }

# ============================================================
# STARTUP: Precarga automática al iniciar
# ============================================================# === SELF KEEP-ALIVE ===
def self_ping_loop():
    import time
    import requests
    time.sleep(10)
    port = int(os.getenv("PORT", 8000))
    url = f"http://127.0.0.1:{port}/ping"
    while True:
        try:
            resp = requests.get(url, timeout=5)
            logger.info(f"Self-ping: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Self-ping failed: {e}")
        time.sleep(14 * 60)

@app.on_event("startup")
async def startup_event():
    def run_precache():
        time.sleep(3)
        precache_daily_data()

    def run_keepalive():
        time.sleep(5)
        self_ping_loop()

    thread = threading.Thread(target=run_precache, daemon=True)
    thread.start()

    if os.getenv("RENDER"):
        keepalive_thread = threading.Thread(target=run_keepalive, daemon=True)
        keepalive_thread.start()
        logger.info("Self keep-alive activado")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
