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

app = FastAPI(title="TipFactory", version="8.0.0")

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

# Mapeo de códigos football-data a IDs de API-Football
# IDs oficiales de API-Football (estables)
LEAGUE_IDS = {
    "PL": 39,      # Premier League
    "PD": 140,     # La Liga
    "SA": 135,     # Serie A
    "BL1": 78,     # Bundesliga
    "FL1": 61,     # Ligue 1
    "PPL": 94,     # Primeira Liga
    "DED": 88,     # Eredivisie
    "BSA": 71,     # Brasileirao
    "CL": 2,       # Champions League
    "EL": 3,       # Europa League
}

COMPETITIONS = {
    "PD": "La Liga",
    "PL": "Premier League",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "PPL": "Primeira Liga",
    "DED": "Eredivisie",
    "BSA": "Brasileirao",
    "CL": "Champions League",
    "EL": "Europa League"
}

DEFAULT_COMPETITIONS = ["PD", "PL", "SA", "BL1", "FL1", "PPL", "DED", "BSA", "CL", "EL"]


def cache_get(key, ttl=1800):
    if key in CACHE:
        data, ts = CACHE[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None


def cache_set(key, data):
    CACHE[key] = (data, datetime.now())


def api_get(endpoint, params=None, cache_key=None, ttl=1800):
    if cache_key:
        cached = cache_get(cache_key, ttl)
        if cached is not None:
            return cached

    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
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

        # API-Football devuelve {"response": [...], "results": N}
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


def format_match(m):
    """Formatea partido desde football-data.org (se mantiene para lista de partidos)"""
    home = m.get("homeTeam", {}) or {}
    away = m.get("awayTeam", {}) or {}
    competition = m.get("competition", {}) or {}
    area = m.get("area", {}) or competition.get("area", {}) or {}
    score = m.get("score", {}) or {}
    ft = score.get("fullTime", {}) if isinstance(score, dict) else {}
    ht = score.get("halfTime", {}) if isinstance(score, dict) else {}

    status = m.get("status", "SCHEDULED")
    status_map = {
        "SCHEDULED": "NS",
        "TIMED": "NS",
        "LIVE": "LIVE",
        "IN_PLAY": "1H",
        "PAUSED": "HT",
        "FINISHED": "FT",
        "POSTPONED": "PST",
        "SUSPENDED": "SUSP",
        "CANCELLED": "CANC",
        "AWARDED": "AWD"
    }

    return {
        "id": m.get("id"),
        "utcDate": m.get("utcDate"),
        "matchDate": (m.get("utcDate") or "")[:10],
        "status": status_map.get(status, status),
        "statusText": status,
        "minute": m.get("minute", 0) if isinstance(m.get("minute", 0), int) else 0,
        "venue": m.get("venue", ""),
        "matchday": m.get("matchday", 0),
        "homeTeam": {
            "id": home.get("id"),
            "name": home.get("name", "Local"),
            "shortName": home.get("shortName", home.get("name", "Local")[:15]),
            "crest": home.get("crest", "")
        },
        "awayTeam": {
            "id": away.get("id"),
            "name": away.get("name", "Visitante"),
            "shortName": away.get("shortName", away.get("name", "Visitante")[:15]),
            "crest": away.get("crest", "")
        },
        "competition": {
            "id": competition.get("id"),
            "name": competition.get("name", ""),
            "code": competition.get("code", "")
        },
        "league_name": competition.get("name", ""),
        "country": area.get("name", ""),
        "homeScore": ft.get("home") if isinstance(ft, dict) else None,
        "awayScore": ft.get("away") if isinstance(ft, dict) else None,
        "halfTimeHome": ht.get("home") if isinstance(ht, dict) else None,
        "halfTimeAway": ht.get("away") if isinstance(ht, dict) else None
    }


def get_team_stats_api_football(team_id, league_id, season):
    """
    Obtiene estadísticas de equipo desde API-Football v3
    Endpoint: /teams/statistics?team={id}&league={id}&season={year}
    """
    if not team_id or not league_id or not season:
        return None

    data = api_get(
        "teams/statistics",
        params={"team": team_id, "league": league_id, "season": season},
        cache_key=f"team_stats_{team_id}_{league_id}_{season}",
        ttl=3600
    )

    if not data or not isinstance(data, dict):
        return None

    response = data.get("response", {})
    if not response:
        return None

    # Extraer datos de estadísticas
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

    # Goles
    goals_for = safe_get(goals, "for", "total", "total", default=0)
    goals_against = safe_get(goals, "against", "total", "total", default=0)

    # Calcular medias
    avg_gf = round(goals_for / played, 2) if played else 0
    avg_ga = round(goals_against / played, 2) if played else 0
    avg_total = round((goals_for + goals_against) / played, 2) if played else 0

    # Forma (últimos 5 partidos)
    form_list = []
    for char in form[-5:] if form else []:
        if char == "W":
            form_list.append({"result": "W", "result_text": "Victoria"})
        elif char == "D":
            form_list.append({"result": "D", "result_text": "Empate"})
        elif char == "L":
            form_list.append({"result": "L", "result_text": "Derrota"})

    # Estimar Over/BTTS desde goles (API-Football no da estos directamente en team stats)
    # Usamos heurística: si avg_total > 2.5, Over 2.5 es probable
    est_over_15 = min(100, round(avg_total * 35, 1))
    est_over_25 = min(100, round(avg_total * 25, 1))
    est_over_35 = min(100, round(avg_total * 15, 1))
    est_btts = min(100, round((avg_gf / max(avg_gf + 0.5, 0.1)) * (avg_ga / max(avg_ga + 0.5, 0.1)) * 100, 1))

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
        "clean_sheet_pct": round((clean_sheet.get("total", 0) / played) * 100, 1) if played else 0,
        "failed_to_score_pct": round((failed_to_score.get("total", 0) / played) * 100, 1) if played else 0,
        "form_string": form,
        "form": form_list,
        "biggest_win": safe_get(biggest, "wins", default=""),
        "biggest_loss": safe_get(biggest, "loses", default="")
    }


def get_standings_api_football(league_id, season):
    """
    Obtiene clasificación desde API-Football v3
    Endpoint: /standings?league={id}&season={year}
    """
    if not league_id or not season:
        return None

    data = api_get(
        "standings",
        params={"league": league_id, "season": season},
        cache_key=f"standings_{league_id}_{season}",
        ttl=3600
    )

    if not data or not isinstance(data, dict):
        return None

    response = data.get("response", [])
    if not response or not isinstance(response, list):
        return None

    # La respuesta tiene league, season, standings[]
    standings_data = response[0] if response else {}
    standings_list = standings_data.get("league", {}).get("standings", [[]])
    
    # standings_list es una lista de grupos (para ligas con grupos)
    all_teams = []
    for group in standings_list:
        if isinstance(group, list):
            all_teams.extend(group)

    return all_teams


def find_team_in_standings(standings, team_id):
    """Busca un equipo en la clasificación por ID"""
    if not standings or not team_id:
        return None
    
    for team_data in standings:
        if team_data.get("team", {}).get("id") == team_id:
            return {
                "position": team_data.get("rank", 0),
                "playedGames": team_data.get("all", {}).get("played", 0),
                "won": team_data.get("all", {}).get("win", 0),
                "draw": team_data.get("all", {}).get("draw", 0),
                "lost": team_data.get("all", {}).get("lose", 0),
                "goalsFor": team_data.get("all", {}).get("goals", {}).get("for", 0),
                "goalsAgainst": team_data.get("all", {}).get("goals", {}).get("against", 0),
                "points": team_data.get("points", 0),
                "form": team_data.get("form", "")
            }
    return None


def get_h2h_api_football(team1_id, team2_id, last=5):
    """
    Obtiene H2H desde API-Football v3
    Endpoint: /fixtures/headtohead?h2h={id}-{id}
    """
    if not team1_id or not team2_id:
        return [], {}

    data = api_get(
        "fixtures/headtohead",
        params={"h2h": f"{team1_id}-{team2_id}", "last": last},
        cache_key=f"h2h_{team1_id}_{team2_id}",
        ttl=3600
    )

    if not data or not isinstance(data, dict):
        return [], {}

    fixtures = data.get("response", [])
    if not fixtures:
        return [], {}

    matches = []
    home_wins = away_wins = draws = 0
    home_goals = away_goals = 0

    for f in fixtures:
        teams = f.get("teams", {})
        goals = f.get("goals", {})
        
        home_team = teams.get("home", {})
        away_team = teams.get("away", {})
        
        hg = goals.get("home")
        ag = goals.get("away")

        matches.append({
            "date": f.get("fixture", {}).get("date", "")[:10],
            "home": home_team.get("name", ""),
            "away": away_team.get("name", ""),
            "homeScore": hg,
            "awayScore": ag,
            "competition": f.get("league", {}).get("name", "")
        })

        if hg is not None and ag is not None:
            home_goals += hg
            away_goals += ag
            if hg > ag:
                home_wins += 1
            elif hg == ag:
                draws += 1
            else:
                away_wins += 1

    stats = {
        "home_wins": home_wins,
        "away_wins": away_wins,
        "draws": draws,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "total_matches": len(fixtures)
    }

    return matches, stats


def get_predictions_api_football(fixture_id):
    """
    Obtiene predicciones desde API-Football v3
    Endpoint: /predictions?fixture={id}
    """
    if not fixture_id:
        return None

    data = api_get(
        "predictions",
        params={"fixture": fixture_id},
        cache_key=f"predictions_{fixture_id}",
        ttl=1800
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


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/matches")
def api_matches(date: str = Query(None)):
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    collected = []
    found = []

    # Usar football-data.org para partidos del día (más estable para fixtures)
    for code in DEFAULT_COMPETITIONS:
        data = api_get(
            "competitions/{code}/matches".replace("{code}", code),
            base_url="https://api.football-data.org/v4",
            headers={"X-Auth-Token": os.getenv("API_FOOTBALL_KEY", "")},
            params={"dateFrom": date, "dateTo": date},
            cache_key=f"matches_{code}_{date}",
            ttl=1800
        )

        if data and isinstance(data, dict) and data.get("matches"):
            comp_matches = [format_match(m) for m in data["matches"]]
            comp_matches = [m for m in comp_matches if m["matchDate"] == date]
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
        "source": "football-data.org"
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
    matchday: int = Query(0),
    status: str = Query("SCHEDULED")
):
    logger.info(f"=== ANALYZE match_id={match_id}, home={home_team}, away={away_team} ===")
    
    # === OBTENER LEAGUE ID Y SEASON ===
    comp_code = None
    for code, name in COMPETITIONS.items():
        if name.lower() in (league or "").lower():
            comp_code = code
            break
    
    league_id = LEAGUE_IDS.get(comp_code) if comp_code else None
    season = datetime.utcnow().year
    
    logger.info(f"Comp code: {comp_code}, League ID: {league_id}, Season: {season}")

    # === ESTADÍSTICAS DE EQUIPOS (API-Football) ===
    home_stats = None
    away_stats = None
    home_mode = "NO_DATA"
    away_mode = "NO_DATA"

    if league_id:
        logger.info(f"Fetching API-Football stats for league {league_id}, season {season}")
        
        home_stats = get_team_stats_api_football(home_id, league_id, season)
        away_stats = get_team_stats_api_football(away_id, league_id, season)
        
        if home_stats and home_stats["played"] > 0:
            home_mode = "API_FOOTBALL"
        if away_stats and away_stats["played"] > 0:
            away_mode = "API_FOOTBALL"

    # === STANDINGS ===
    standings = get_standings_api_football(league_id, season) if league_id else None
    
    home_table = find_team_in_standings(standings, home_id) if standings else None
    away_table = find_team_in_standings(standings, away_id) if standings else None

    if not home_table:
        home_table = {"position": 0, "points": 0, "won": 0, "draw": 0, "lost": 0, "goalsFor": 0, "goalsAgainst": 0}
    if not away_table:
        away_table = {"position": 0, "points": 0, "won": 0, "draw": 0, "lost": 0, "goalsFor": 0, "goalsAgainst": 0}

    # === H2H ===
    h2h_matches, h2h_stats = get_h2h_api_football(home_id, away_id, last=5)

    # === PREDICCIONES ===
    predictions = get_predictions_api_football(match_id)

    # === SI NO HAY STATS, USAR STANDINGS COMO FALLBACK ===
    if not home_stats or home_stats["played"] == 0:
        home_stats = {
            "played": home_table.get("playedGames", 0),
            "won": home_table.get("won", 0),
            "draw": home_table.get("draw", 0),
            "lost": home_table.get("lost", 0),
            "goals_for": home_table.get("goalsFor", 0),
            "goals_against": home_table.get("goalsAgainst", 0),
            "avg_total_goals": round((home_table.get("goalsFor", 0) + home_table.get("goalsAgainst", 0)) / max(home_table.get("playedGames", 1), 1), 2),
            "avg_team_goals": round(home_table.get("goalsFor", 0) / max(home_table.get("playedGames", 1), 1), 2),
            "avg_conceded": round(home_table.get("goalsAgainst", 0) / max(home_table.get("playedGames", 1), 1), 2),
            "btts_pct": 0, "over_1_5_pct": 0, "over_2_5_pct": 0, "over_3_5_pct": 0,
            "clean_sheet_pct": 0, "failed_to_score_pct": 0,
            "form_string": home_table.get("form", ""),
            "form": []
        }
        home_mode = "STANDINGS_FALLBACK"

    if not away_stats or away_stats["played"] == 0:
        away_stats = {
            "played": away_table.get("playedGames", 0),
            "won": away_table.get("won", 0),
            "draw": away_table.get("draw", 0),
            "lost": away_table.get("lost", 0),
            "goals_for": away_table.get("goalsFor", 0),
            "goals_against": away_table.get("goalsAgainst", 0),
            "avg_total_goals": round((away_table.get("goalsFor", 0) + away_table.get("goalsAgainst", 0)) / max(away_table.get("playedGames", 1), 1), 2),
            "avg_team_goals": round(away_table.get("goalsFor", 0) / max(away_table.get("playedGames", 1), 1), 2),
            "avg_conceded": round(away_table.get("goalsAgainst", 0) / max(away_table.get("playedGames", 1), 1), 2),
            "btts_pct": 0, "over_1_5_pct": 0, "over_2_5_pct": 0, "over_3_5_pct": 0,
            "clean_sheet_pct": 0, "failed_to_score_pct": 0,
            "form_string": away_table.get("form", ""),
            "form": []
        }
        away_mode = "STANDINGS_FALLBACK"

    # Probabilidades
    probabilities = {
        "over_1_5": round((home_stats["over_1_5_pct"] + away_stats["over_1_5_pct"]) / 2, 1) if home_stats["played"] and away_stats["played"] else 0.0,
        "over_2_5": round((home_stats["over_2_5_pct"] + away_stats["over_2_5_pct"]) / 2, 1) if home_stats["played"] and away_stats["played"] else 0.0,
        "over_3_5": round((home_stats["over_3_5_pct"] + away_stats["over_3_5_pct"]) / 2, 1) if home_stats["played"] and away_stats["played"] else 0.0,
        "btts": round((home_stats["btts_pct"] + away_stats["btts_pct"]) / 2, 1) if home_stats["played"] and away_stats["played"] else 0.0,
        "total_expected_goals": round(home_stats["avg_team_goals"] + away_stats["avg_team_goals"], 2) if home_stats["played"] and away_stats["played"] else 0,
        "home_xg": 0,
        "away_xg": 0
    }

    # Odds desde predicciones si existen
    odds = {
        "home": 0,
        "draw": 0,
        "away": 0
    }
    if predictions:
        try:
            odds["home"] = float(predictions.get("percent_home", "0").replace("%", "")) / 100 if predictions.get("percent_home") else 0
            odds["draw"] = float(predictions.get("percent_draw", "0").replace("%", "")) / 100 if predictions.get("percent_draw") else 0
            odds["away"] = float(predictions.get("percent_away", "0").replace("%", "")) / 100 if predictions.get("percent_away") else 0
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
        "table_stats": {
            "home": home_table,
            "away": away_table
        },
        "h2h": {
            "matches": h2h_matches,
            "stats": h2h_stats
        },
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
        "version": "8.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
