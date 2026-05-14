import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict

import requests
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="TipFactory", version="11.0.0")

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
API_KEY = "247e8b9eb521d5081463f72ca03ca37b"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

CACHE = {}

# === LIGAS SOPORTADAS ===
LEAGUE_IDS = {
    "PL": 39, "PD": 140, "SA": 135, "BL1": 78, "FL1": 61,
    "PPL": 94, "DED": 88, "ELC": 40, "SP": 207, "SI": 131,
    "SD": 81, "FL2": 62, "BSA": 71, "CLI": 13, "CSA": 11,
    "ARG": 128, "COL": 239, "CHI": 265, "URU": 268, "PAR": 252,
    "ECU": 242, "PER": 281, "VEN": 277, "BOL": 344, "BRA_B": 72,
    "ARG_B": 129, "MX": 262, "MLS": 253, "MX_B": 263,
    "JP": 98, "KR": 292, "CN": 169, "AU_A": 113, "IN": 323,
    "TH": 295, "SA_A": 307, "AE": 301, "QA": 340, "IR": 291,
    "JP_B": 99, "KR_B": 293, "CN_B": 170, "IDN": 274, "MYS": 274,
    "SGP": 275, "VNM": 276, "EG": 233, "ZA": 289, "MA": 200,
    "TN": 194, "DZ": 186, "NG": 371, "GH": 376, "BE": 144,
    "CH": 207, "AU": 218, "DK": 119, "NO": 103, "FI": 244,
    "CZ": 346, "GR": 197, "TR": 203, "UA": 333, "HR": 210,
    "RO": 283, "SC": 180, "RU": 235, "PLN": 106, "CRC": 163,
    "GT": 370, "HN": 300, "SV": 279, "PA": 287, "JM": 357,
    "USL": 255, "CAN": 259, "CL": 2, "EL": 3, "ECL": 848,
    "WC": 1, "EURO": 4, "COPA": 9, "AFCON": 6, "GOLD": 22,
    "ASIA": 7, "NATIONS": 5, "WCC": 10,
}

COMPETITIONS = {
    "PL": "Premier League", "PD": "La Liga", "SA": "Serie A",
    "BL1": "Bundesliga", "FL1": "Ligue 1", "PPL": "Primeira Liga",
    "DED": "Eredivisie", "ELC": "Championship", "SP": "La Liga 2",
    "SI": "Serie B", "SD": "2. Bundesliga", "FL2": "Ligue 2",
    "BSA": "Brasileirao", "CLI": "Copa Libertadores", "CSA": "Copa Sudamericana",
    "ARG": "Liga Argentina", "COL": "Liga Colombia", "MX": "Liga MX",
    "MLS": "MLS", "JP": "J1 League", "KR": "K League",
    "SA_A": "Pro League Saudi", "EG": "Premier League Egypt",
    "WC": "World Cup", "EURO": "Euro", "CL": "Champions League",
    "EL": "Europa League", "ECL": "Conference League",
    "NATIONS": "Nations League", "AFCON": "Africa Cup",
    "COPA": "Copa América", "GOLD": "Gold Cup", "ASIA": "Asian Cup",
    "BRA_B": "Série B Brasil", "ARG_B": "Primera Nacional",
    "MX_B": "Liga Expansión MX", "JP_B": "J2 League",
    "KR_B": "K League 2", "CN": "Super League China",
    "AU_A": "A-League", "IN": "ISL India", "TH": "Thai League",
    "ZA": "Premier Division RSA", "MA": "Botola Pro",
    "TN": "Ligue 1 Túnez", "DZ": "Ligue 1 Argelia",
    "NG": "NPFL Nigeria", "GH": "Premier League Ghana",
    "BE": "Jupiler Pro League", "CH": "Super League Suiza",
    "AU": "Bundesliga Austria", "DK": "Superliga Dinamarca",
    "NO": "Eliteserien", "FI": "Veikkausliiga",
    "CZ": "First League Checa", "GR": "Super League Grecia",
    "TR": "Süper Lig", "UA": "Premier League Ucrania",
    "HR": "HNL Croacia", "RO": "Liga I Rumanía",
    "SC": "Premiership Escocia", "RU": "Premier League Rusia",
    "PLN": "Ekstraklasa Polonia", "ECU": "Serie A Ecuador",
    "PER": "Liga 1 Perú", "CHI": "Primera División Chile",
    "URU": "Primera División Uruguay", "PAR": "Primera División Paraguay",
    "VEN": "Primera División Venezuela", "BOL": "División Profesional Bolivia",
    "CRC": "Primera División Costa Rica", "GT": "Liga Nacional Guatemala",
    "HN": "Liga Nacional Honduras", "SV": "Primera División El Salvador",
    "PA": "LPF Panamá", "JM": "Premier League Jamaica",
    "USL": "USL Championship", "CAN": "Canadian Premier League",
    "IR": "Persian Gulf Pro League", "QA": "Stars League Qatar",
    "AE": "UAE Pro League", "IDN": "Liga 1 Indonesia",
    "MYS": "Super League Malasia", "SGP": "Premier League Singapur",
    "VNM": "V.League 1", "WCC": "FIFA Club World Cup",
}

DEFAULT_COMPETITIONS = [
    "PD", "PL", "SA", "BL1", "FL1", "PPL", "DED", "BSA", "CL", "EL",
    "ARG", "COL", "MX", "MLS", "JP", "KR", "SA_A", "EG", "ZA", "MA",
    "BE", "CH", "AU", "DK", "NO", "FI", "CZ", "GR", "TR", "UA",
    "HR", "RO", "SC", "RU", "PLN", "ECU", "PER", "CHI", "URU", "PAR",
    "VEN", "BOL", "CRC", "GT", "HN", "SV", "PA", "JM", "USL", "CAN",
    "IR", "QA", "AE", "IDN", "MYS", "SGP", "VNM", "ECL", "NATIONS",
    "AFCON", "COPA", "GOLD", "ASIA", "BRA_B", "ARG_B", "MX_B", "JP_B",
    "KR_B", "CN", "AU_A", "IN", "TH", "NG", "GH", "TN", "DZ", "ELC",
    "SP", "SI", "SD", "FL2", "WC", "EURO", "WCC",
]


def cache_get(key, ttl=3600):
    if key in CACHE:
        data, ts = CACHE[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None


def cache_set(key, data):
    CACHE[key] = (data, datetime.now())


def api_get(endpoint, params=None, cache_key=None, ttl=3600):
    if cache_key:
        cached = cache_get(cache_key, ttl)
        if cached is not None:
            return cached

    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}/"
        logger.info(f"API CALL: {url} | params={params}")
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)

        if resp.status_code == 429:
            logger.warning("RATE LIMIT API-Football")
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
    now = datetime.utcnow()
    if now.month >= 7:
        return now.year
    else:
        return now.year - 1


# ============================================================
# DATOS REALES DE LA API: FIXTURES + STATISTICS
# ============================================================

def get_team_fixtures_real(team_id, league_id, season, last=15):
    """
    Obtiene últimos partidos JUGADOS del equipo (FT, AET, PEN).
    Endpoint: /fixtures?team={id}&league={id}&season={year}&last={n}&status=ft
    """
    if not team_id or not league_id or not season:
        return []

    data = api_get(
        "fixtures",
        params={
            "team": team_id,
            "league": league_id,
            "season": season,
            "last": last,
            "status": "ft"
        },
        cache_key=f"team_fixtures_ft_{team_id}_{league_id}_{season}_{last}",
        ttl=3600
    )

    if not data or not isinstance(data, dict):
        return []

    return data.get("response", [])


def get_fixtures_statistics_batch(fixture_ids):
    """
    Obtiene estadísticas de múltiples partidos de golpe.
    La API permite hasta 20 fixtures por llamada.
    Endpoint: /fixtures/statistics?fixture={id1}-{id2}-...-{idN}
    """
    if not fixture_ids:
        return {}

    # La API acepta múltiples IDs separados por guión
    ids_str = "-".join(str(fid) for fid in fixture_ids[:20])

    data = api_get(
        "fixtures/statistics",
        params={"fixture": ids_str},
        cache_key=f"fixtures_stats_batch_{ids_str}",
        ttl=3600
    )

    if not data or not isinstance(data, dict):
        return {}

    # Organizar por fixture_id y team_id
    result = {}
    for item in data.get("response", []):
        fixture_id = item.get("fixture", {}).get("id")
        team_id = item.get("team", {}).get("id")
        stats = item.get("statistics", [])

        if fixture_id not in result:
            result[fixture_id] = {}

        parsed = {}
        for stat in stats:
            stat_type = stat.get("type", "").lower().replace(" ", "_")
            value = stat.get("value")
            parsed[stat_type] = value

        result[fixture_id][team_id] = parsed

    return result


def calculate_real_stats_from_fixtures(fixtures, team_id, stats_by_fixture):
    """
    Calcula estadísticas REALES desde los partidos jugados.
    Devuelve goles, corners, tarjetas, tiros, posesión, etc.
    """
    if not fixtures:
        return None

    total_goals_for = 0
    total_goals_against = 0
    total_corners = 0
    total_yellow = 0
    total_red = 0
    total_shots = 0
    total_shots_on = 0
    total_possession = 0
    total_fouls = 0
    matches_with_stats = 0
    matches_with_goals = 0

    # Para calcular porcentajes de over/under/btts
    over_15_count = 0
    over_25_count = 0
    over_35_count = 0
    btts_count = 0
    clean_sheet_count = 0
    failed_score_count = 0

    for fixture in fixtures:
        fixture_id = fixture.get("fixture", {}).get("id")
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})

        home_team = teams.get("home", {})
        away_team = teams.get("away", {})
        is_home = home_team.get("id") == team_id

        home_goals = goals.get("home", 0) or 0
        away_goals = goals.get("away", 0) or 0

        if is_home:
            gf = home_goals
            ga = away_goals
        else:
            gf = away_goals
            ga = home_goals

        total_goals = gf + ga

        # Contar goles
        total_goals_for += gf
        total_goals_against += ga
        matches_with_goals += 1

        # Over/Under/BTTS reales
        if total_goals > 1.5:
            over_15_count += 1
        if total_goals > 2.5:
            over_25_count += 1
        if total_goals > 3.5:
            over_35_count += 1
        if gf > 0 and ga > 0:
            btts_count += 1
        if ga == 0:
            clean_sheet_count += 1
        if gf == 0:
            failed_score_count += 1

        # Estadísticas detalladas del partido
        fixture_stats = stats_by_fixture.get(fixture_id, {})
        team_stats = fixture_stats.get(team_id, {})

        if team_stats:
            matches_with_stats += 1

            # Corners
            corners = team_stats.get("corner_kicks")
            if corners is not None:
                try:
                    total_corners += int(corners)
                except:
                    pass

            # Tarjetas amarillas
            yellow = team_stats.get("yellow_cards")
            if yellow is not None:
                try:
                    total_yellow += int(yellow)
                except:
                    pass

            # Tarjetas rojas
            red = team_stats.get("red_cards")
            if red is not None:
                try:
                    total_red += int(red)
                except:
                    pass

            # Tiros
            shots = team_stats.get("total_shots")
            if shots is not None:
                try:
                    total_shots += int(shots)
                except:
                    pass

            # Tiros a puerta
            shots_on = team_stats.get("shots_on_goal")
            if shots_on is not None:
                try:
                    total_shots_on += int(shots_on)
                except:
                    pass

            # Posesión
            possession = team_stats.get("ball_possession")
            if possession is not None:
                try:
                    # Puede venir como "45%" o 45
                    if isinstance(possession, str):
                        possession = int(possession.replace("%", ""))
                    total_possession += int(possession)
                except:
                    pass

            # Faltas
            fouls = team_stats.get("fouls")
            if fouls is not None:
                try:
                    total_fouls += int(fouls)
                except:
                    pass

    played = matches_with_goals
    if played == 0:
        return None

    # Calcular medias
    avg_gf = round(total_goals_for / played, 2)
    avg_ga = round(total_goals_against / played, 2)
    avg_total = round((total_goals_for + total_goals_against) / played, 2)

    avg_corners = round(total_corners / matches_with_stats, 2) if matches_with_stats else 0
    avg_yellow = round(total_yellow / matches_with_stats, 2) if matches_with_stats else 0
    avg_red = round(total_red / matches_with_stats, 2) if matches_with_stats else 0
    avg_shots = round(total_shots / matches_with_stats, 2) if matches_with_stats else 0
    avg_shots_on = round(total_shots_on / matches_with_stats, 2) if matches_with_stats else 0
    avg_possession = round(total_possession / matches_with_stats, 2) if matches_with_stats else 0
    avg_fouls = round(total_fouls / matches_with_stats, 2) if matches_with_stats else 0

    # Porcentajes reales (frecuencias)
    over_15_pct = round((over_15_count / played) * 100, 1)
    over_25_pct = round((over_25_count / played) * 100, 1)
    over_35_pct = round((over_35_count / played) * 100, 1)
    btts_pct = round((btts_count / played) * 100, 1)
    clean_sheet_pct = round((clean_sheet_count / played) * 100, 1)
    failed_score_pct = round((failed_score_count / played) * 100, 1)

    return {
        "played": played,
        "goals_for": total_goals_for,
        "goals_against": total_goals_against,
        "avg_team_goals": avg_gf,
        "avg_conceded": avg_ga,
        "avg_total_goals": avg_total,
        "avg_corners": avg_corners,
        "avg_yellow_cards": avg_yellow,
        "avg_red_cards": avg_red,
        "avg_total_cards": round(avg_yellow + avg_red, 2),
        "avg_shots": avg_shots,
        "avg_shots_on": avg_shots_on,
        "avg_possession": avg_possession,
        "avg_fouls": avg_fouls,
        "over_1_5_pct": over_15_pct,
        "over_2_5_pct": over_25_pct,
        "over_3_5_pct": over_35_pct,
        "btts_pct": btts_pct,
        "clean_sheet_pct": clean_sheet_pct,
        "failed_to_score_pct": failed_score_pct,
        "matches_with_stats": matches_with_stats,
    }


def get_team_stats_real(team_id, league_id, season):
    """
    Obtiene estadísticas REALES del equipo desde partidos jugados.
    1. Obtiene últimos 15 partidos FT
    2. Obtiene estadísticas de esos partidos (batch)
    3. Calcula medias y porcentajes reales
    """
    if not team_id or not league_id or not season:
        return None

    # 1. Partidos jugados
    fixtures = get_team_fixtures_real(team_id, league_id, season, last=15)
    if not fixtures:
        return None

    # 2. IDs de fixtures para batch
    fixture_ids = [f.get("fixture", {}).get("id") for f in fixtures if f.get("fixture", {}).get("id")]

    # 3. Estadísticas en batch
    stats_by_fixture = get_fixtures_statistics_batch(fixture_ids)

    # 4. Calcular estadísticas reales
    return calculate_real_stats_from_fixtures(fixtures, team_id, stats_by_fixture)


# ============================================================
# PREDICCIONES
# ============================================================

def get_predictions(fixture_id):
    if not fixture_id:
        return None

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

    return {
        "winner": predictions.get("winner", {}).get("name", ""),
        "winner_comment": predictions.get("winner", {}).get("comment", ""),
        "under_over": predictions.get("under_over", ""),
        "advice": predictions.get("advice", ""),
        "percent_home": safe_get(comparison, "home", default=""),
        "percent_draw": safe_get(comparison, "draw", default=""),
        "percent_away": safe_get(comparison, "away", default="")
    }


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
        ttl=1800
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
            last_part = parts[-1].strip()
            try:
                matchday = int(last_part)
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
        "halfTimeHome": None,
        "halfTimeAway": None,
        "api_football_fixture_id": fixture.get("id")
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/matches")
def api_matches(date: str = Query(None)):
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    season = get_season()
    collected = []
    found = []

    for code in DEFAULT_COMPETITIONS:
        league_id = get_league_id(code)
        if not league_id:
            continue

        fixtures = get_fixtures_by_date(date, league_id=league_id, season=season)

        if fixtures:
            comp_matches = [format_fixture(f) for f in fixtures]
            if comp_matches:
                collected.extend(comp_matches)
                found.append({"code": code, "name": COMPETITIONS.get(code, code)})

    seen = set()
    unique = []
    for m in collected:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)

    unique.sort(key=lambda x: x.get("utcDate", ""))

    return {
        "matches": unique,
        "requested_date": date,
        "source_date": date if unique else None,
        "is_exact": True,
        "competitions_found": found,
        "source": "api-football.com"
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

    logger.info(f"Comp: {comp_code}, League ID: {league_id}, Season: {season}")

    # === ESTADÍSTICAS REALES DESDE PARTIDOS JUGADOS ===
    # Cada equipo: 1 llamada a fixtures + 1 batch de statistics
    # Total por análisis: 2 llamadas para stats + 1 para predicciones = 3 llamadas

    home_stats = get_team_stats_real(home_id, league_id, season) if league_id else None
    away_stats = get_team_stats_real(away_id, league_id, season) if league_id else None

    home_mode = "REAL" if (home_stats and home_stats["played"] > 0) else "NO_DATA"
    away_mode = "REAL" if (away_stats and away_stats["played"] > 0) else "NO_DATA"

    # Forma (últimos 5 resultados) desde /teams/statistics (1 llamada extra, cacheada)
    home_form_data = api_get(
        "teams/statistics",
        params={"team": home_id, "league": league_id, "season": season},
        cache_key=f"team_stats_form_{home_id}_{league_id}_{season}",
        ttl=7200
    )
    away_form_data = api_get(
        "teams/statistics",
        params={"team": away_id, "league": league_id, "season": season},
        cache_key=f"team_stats_form_{away_id}_{league_id}_{season}",
        ttl=7200
    )

    def parse_form(form_data):
        if not form_data or not isinstance(form_data, dict):
            return []
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

    # FALLBACK si no hay datos reales
    if not home_stats or home_stats["played"] == 0:
        home_stats = {
            "played": 0, "goals_for": 0, "goals_against": 0,
            "avg_team_goals": 1.25, "avg_conceded": 1.25, "avg_total_goals": 2.5,
            "avg_corners": 4.5, "avg_yellow_cards": 2.0, "avg_red_cards": 0.15,
            "avg_total_cards": 2.15, "avg_shots": 10, "avg_shots_on": 4,
            "avg_possession": 50, "avg_fouls": 12,
            "over_1_5_pct": 70, "over_2_5_pct": 50, "over_3_5_pct": 25,
            "btts_pct": 50, "clean_sheet_pct": 20, "failed_to_score_pct": 20,
            "matches_with_stats": 0,
        }
        home_mode = "DEFAULT"

    if not away_stats or away_stats["played"] == 0:
        away_stats = {
            "played": 0, "goals_for": 0, "goals_against": 0,
            "avg_team_goals": 1.25, "avg_conceded": 1.25, "avg_total_goals": 2.5,
            "avg_corners": 4.5, "avg_yellow_cards": 2.0, "avg_red_cards": 0.15,
            "avg_total_cards": 2.15, "avg_shots": 10, "avg_shots_on": 4,
            "avg_possession": 50, "avg_fouls": 12,
            "over_1_5_pct": 70, "over_2_5_pct": 50, "over_3_5_pct": 25,
            "btts_pct": 50, "clean_sheet_pct": 20, "failed_to_score_pct": 20,
            "matches_with_stats": 0,
        }
        away_mode = "DEFAULT"

    # PREDICCIONES
    predictions = get_predictions(match_id)

    # PROBABILIDADES (promedio de los dos equipos)
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
            "home_stats_played": home_stats["played"],
            "away_stats_played": away_stats["played"]
        }
    })


@app.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "cache_size": len(CACHE),
        "api_football": "configured",
        "version": "11.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
