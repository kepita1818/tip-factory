import os
import logging
from datetime import datetime, timedelta

import requests
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="TipFactory", version="10.1.0")

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


def estimate_corners_and_cards(goals_for, goals_against, played, avg_total_goals):
    """
    Estima corners y tarjetas basándose en el ESTILO DE JUEGO del equipo.

    - Equipos ofensivos (muchos goles) → más corners, más tarjetas (presión alta)
    - Equipos defensivos (pocos goles) → menos corners, menos tarjetas
    - Equipos físicos (muchos goles encajados = muchos duelos) → más tarjetas

    Fórmulas ajustadas para valores REALISTAS:
    - Corners: base 4.0 + factor ofensivo + factor posesión
    - Tarjetas amarillas: base 1.8 + factor físico + factor presión
    - Tarjetas rojas: base 0.12 + factor agresividad
    """
    if played == 0 or avg_total_goals == 0:
        return {
            "avg_corners": 4.5,
            "avg_yellow_cards": 2.0,
            "avg_red_cards": 0.15,
            "avg_total_cards": 2.15
        }

    avg_gf = goals_for / played
    avg_ga = goals_against / played

    # Factor ofensivo: cuánto ataca el equipo (0.5 a 2.0)
    offensive_factor = 0.7 + (avg_gf / 2.0)
    offensive_factor = min(2.0, max(0.5, offensive_factor))

    # Factor defensivo: cuánto le atacan (0.5 a 2.0)
    defensive_factor = 0.7 + (avg_ga / 2.0)
    defensive_factor = min(2.0, max(0.5, defensive_factor))

    # Factor físico/agresividad: combinación de goles totales (partidos intensos)
    intensity_factor = avg_total_goals / 2.5  # normalizado
    intensity_factor = min(1.5, max(0.7, intensity_factor))

    # CORNERS: equipos que atacan mucho hacen más corners
    # Base 4.0, escalado por factor ofensivo y defensivo
    est_corners = 4.0 + (avg_gf * 1.2) + (avg_ga * 0.4)
    est_corners = est_corners * (0.9 + (offensive_factor * 0.1))
    est_corners = round(min(14.0, max(3.0, est_corners)), 2)

    # TARJETAS AMARILLAS: equipos físicos/intensos reciben más
    # Base 1.8, escalado por intensidad del juego
    est_yellow = 1.8 + (avg_total_goals * 0.35) + (avg_ga * 0.25)
    est_yellow = est_yellow * intensity_factor
    est_yellow = round(min(5.0, max(1.0, est_yellow)), 2)

    # TARJETAS ROJAS: equipos agresivos o desesperados
    # Base 0.12, ligero incremento con intensidad
    est_red = 0.12 + (avg_ga * 0.02) + (intensity_factor * 0.05)
    est_red = round(min(0.8, max(0.05, est_red)), 2)

    return {
        "avg_corners": est_corners,
        "avg_yellow_cards": est_yellow,
        "avg_red_cards": est_red,
        "avg_total_cards": round(est_yellow + est_red, 2)
    }


def get_team_stats(team_id, league_id, season):
    """Obtiene estadísticas de equipo - SOLO 1 llamada API"""
    if not team_id or not league_id or not season:
        return None

    data = api_get(
        "teams/statistics",
        params={"team": team_id, "league": league_id, "season": season},
        cache_key=f"team_stats_{team_id}_{league_id}_{season}",
        ttl=7200
    )

    if not data or not isinstance(data, dict):
        return None

    response = data.get("response", {})
    if not response:
        return None

    fixtures = response.get("fixtures", {})
    goals = response.get("goals", {})
    biggest = response.get("biggest", {})
    clean_sheet = response.get("clean_sheet", {})
    failed_to_score = response.get("failed_to_score", {})
    form = response.get("form", "")

    played = safe_get(fixtures, "played", "total", default=0)
    wins = safe_get(fixtures, "wins", "total", default=0)
    draws = safe_get(fixtures, "draws", "total", default=0)
    losses = safe_get(fixtures, "loses", "total", default=0)

    goals_for = safe_get(goals, "for", "total", "total", default=0)
    goals_against = safe_get(goals, "against", "total", "total", default=0)

    avg_gf = round(goals_for / played, 2) if played else 0
    avg_ga = round(goals_against / played, 2) if played else 0
    avg_total = round((goals_for + goals_against) / played, 2) if played else 0

    form_list = []
    for char in (form or "")[-5:]:
        if char == "W":
            form_list.append({"result": "W", "result_text": "Victoria"})
        elif char == "D":
            form_list.append({"result": "D", "result_text": "Empate"})
        elif char == "L":
            form_list.append({"result": "L", "result_text": "Derrota"})

    # Cálculos de probabilidad basados en datos reales
    est_over_15 = min(100, round(avg_total * 35, 1)) if avg_total > 0 else 0
    est_over_25 = min(100, round(avg_total * 25, 1)) if avg_total > 0 else 0
    est_over_35 = min(100, round(avg_total * 15, 1)) if avg_total > 0 else 0
    est_btts = min(100, round((avg_gf / max(avg_gf + 0.5, 0.1)) * (avg_ga / max(avg_ga + 0.5, 0.1)) * 100, 1)) if avg_gf > 0 and avg_ga > 0 else 0

    clean_sheets = clean_sheet.get("total", 0) if isinstance(clean_sheet, dict) else 0
    failed_scores = failed_to_score.get("total", 0) if isinstance(failed_to_score, dict) else 0

    # CORNERS Y TARJETAS REALISTAS basados en el estilo de juego
    cc = estimate_corners_and_cards(goals_for, goals_against, played, avg_total)

    return {
        "played": played,
        "won": wins,
        "draw": draws,
        "lost": losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "avg_total_goals": avg_total,
        "avg_team_goals": avg_gf,
        "avg_conceded": avg_ga,
        "btts_pct": est_btts,
        "over_1_5_pct": est_over_15,
        "over_2_5_pct": est_over_25,
        "over_3_5_pct": est_over_35,
        "clean_sheet_pct": round((clean_sheets / played) * 100, 1) if played else 0,
        "failed_to_score_pct": round((failed_scores / played) * 100, 1) if played else 0,
        "form_string": form or "",
        "form": form_list,
        "biggest_win": safe_get(biggest, "wins", default=""),
        "biggest_loss": safe_get(biggest, "loses", default=""),
        "corners_total": round(cc["avg_corners"] * played) if played else 0,
        "yellow_cards": round(cc["avg_yellow_cards"] * played) if played else 0,
        "red_cards": round(cc["avg_red_cards"] * played) if played else 0,
        "avg_corners": cc["avg_corners"],
        "avg_yellow_cards": cc["avg_yellow_cards"],
        "avg_red_cards": cc["avg_red_cards"],
        "avg_total_cards": cc["avg_total_cards"],
        "matches_analyzed": played,
    }


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

    # SOLO 3 LLAMADAS API: stats local, stats visitante, predicciones
    home_stats = get_team_stats(home_id, league_id, season) if league_id else None
    away_stats = get_team_stats(away_id, league_id, season) if league_id else None

    home_mode = "API_FOOTBALL" if (home_stats and home_stats["played"] > 0) else "NO_DATA"
    away_mode = "API_FOOTBALL" if (away_stats and away_stats["played"] > 0) else "NO_DATA"

    # FALLBACK
    if not home_stats or home_stats["played"] == 0:
        home_stats = {
            "played": 0, "won": 0, "draw": 0, "lost": 0,
            "goals_for": 0, "goals_against": 0,
            "avg_total_goals": 2.5, "avg_team_goals": 1.25, "avg_conceded": 1.25,
            "btts_pct": 50, "over_1_5_pct": 70, "over_2_5_pct": 50, "over_3_5_pct": 25,
            "clean_sheet_pct": 20, "failed_to_score_pct": 20,
            "form_string": "", "form": [],
            "biggest_win": "", "biggest_loss": "",
            "corners_total": 0, "yellow_cards": 0, "red_cards": 0,
            "avg_corners": 4.5, "avg_yellow_cards": 2.0, "avg_red_cards": 0.15,
            "avg_total_cards": 2.15, "matches_analyzed": 0,
        }
        home_mode = "DEFAULT"

    if not away_stats or away_stats["played"] == 0:
        away_stats = {
            "played": 0, "won": 0, "draw": 0, "lost": 0,
            "goals_for": 0, "goals_against": 0,
            "avg_total_goals": 2.5, "avg_team_goals": 1.25, "avg_conceded": 1.25,
            "btts_pct": 50, "over_1_5_pct": 70, "over_2_5_pct": 50, "over_3_5_pct": 25,
            "clean_sheet_pct": 20, "failed_to_score_pct": 20,
            "form_string": "", "form": [],
            "biggest_win": "", "biggest_loss": "",
            "corners_total": 0, "yellow_cards": 0, "red_cards": 0,
            "avg_corners": 4.5, "avg_yellow_cards": 2.0, "avg_red_cards": 0.15,
            "avg_total_cards": 2.15, "matches_analyzed": 0,
        }
        away_mode = "DEFAULT"

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
        "home_form": home_stats["form"],
        "away_form": away_stats["form"],
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
        "version": "10.1.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
