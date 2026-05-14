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

app = FastAPI(title="TipFactory", version="5.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY} if API_KEY else {}

CACHE = {}
RATE_LIMIT_UNTIL = None

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


def cache_get(key, ttl=3600):
    if key in CACHE:
        data, ts = CACHE[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None


def cache_set(key, data):
    CACHE[key] = (data, datetime.now())


def api_get(endpoint, params=None, cache_key=None, ttl=3600):
    global RATE_LIMIT_UNTIL
    
    if RATE_LIMIT_UNTIL and datetime.now() < RATE_LIMIT_UNTIL:
        if cache_key:
            cached = cache_get(cache_key, ttl=86400)
            if cached is not None:
                return cached
        logger.warning(f"RATE LIMIT COOLDOWN: skipping {endpoint}")
        return None

    if cache_key:
        cached = cache_get(cache_key, ttl)
        if cached is not None:
            return cached

    if not API_KEY:
        logger.error("API_FOOTBALL_KEY missing")
        return None

    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        logger.info(f"API CALL: {url} | params={params}")
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)

        if resp.status_code == 429:
            RATE_LIMIT_UNTIL = datetime.now() + timedelta(seconds=60)
            logger.error(f"RATE LIMIT HIT on {endpoint}. Cooling down 60s.")
            return None
            
        if resp.status_code in (401, 403, 402):
            logger.error(f"AUTH ERROR {resp.status_code} on {endpoint}: {resp.text[:200]}")
            if cache_key:
                cache_set(cache_key, {"_error": resp.status_code})
            return None

        if resp.status_code == 404:
            logger.warning(f"NOT FOUND {endpoint}")
            return None

        resp.raise_for_status()
        data = resp.json()

        if cache_key:
            cache_set(cache_key, data)

        return data
    except Exception as e:
        logger.error(f"API error on {endpoint}: {e}")
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


def extract_stats_from_standings(table_row, form_string=""):
    """
    Extrae estadísticas estimadas desde la tabla de clasificación.
    Usa goles a favor/contra y partidos jugados para estimar medias.
    """
    if not table_row:
        return None
    
    played = table_row.get("playedGames", 0)
    won = table_row.get("won", 0)
    draw = table_row.get("draw", 0)
    lost = table_row.get("lost", 0)
    gf = table_row.get("goalsFor", 0)
    ga = table_row.get("goalsAgainst", 0)
    points = table_row.get("points", 0)
    
    if played == 0:
        return None
    
    # Calcular medias
    avg_gf = round(gf / played, 2)
    avg_ga = round(ga / played, 2)
    avg_total = round((gf + ga) / played, 2)
    
    # Estimar BTTS y Over basado en goles
    # Si avg_total > 2.5, estimar Over 2.5 alto
    # Si avg_gf > 0 y avg_ga > 0, estimar BTTS alto
    est_btts = min(100, round((avg_gf / max(avg_gf + 0.5, 0.1)) * (avg_ga / max(avg_ga + 0.5, 0.1)) * 100, 1))
    est_over_15 = min(100, round(avg_total * 35, 1))  # Heurística
    est_over_25 = min(100, round(avg_total * 25, 1))
    est_over_35 = min(100, round(avg_total * 15, 1))
    
    # Clean sheet y failed to score desde forma
    clean_sheet_pct = round((max(0, played - ga) / played) * 100, 1) if played else 0
    failed_to_score_pct = round((max(0, played - gf) / played) * 100, 1) if played else 0
    
    # Forma desde string (ej: "WWDLW")
    form = []
    for char in (form_string or "")[-5:]:
        if char == "W":
            form.append({"result": "W", "result_text": "Victoria"})
        elif char == "D":
            form.append({"result": "D", "result_text": "Empate"})
        elif char == "L":
            form.append({"result": "L", "result_text": "Derrota"})
    
    return {
        "played": played,
        "won": won,
        "draw": draw,
        "lost": lost,
        "goals_for": gf,
        "goals_against": ga,
        "avg_total_goals": avg_total,
        "avg_team_goals": avg_gf,
        "avg_conceded": avg_ga,
        "btts_pct": est_btts,
        "over_1_5_pct": est_over_15,
        "over_2_5_pct": est_over_25,
        "over_3_5_pct": est_over_35,
        "clean_sheet_pct": clean_sheet_pct,
        "failed_to_score_pct": failed_to_score_pct,
        "form_string": form_string or "",
        "form": form,
        "points": points,
        "position": table_row.get("position", 0)
    }


def find_team_row(table_rows, team_id):
    for row in table_rows:
        if safe_get(row, "team", "id") == team_id:
            return {
                "position": row.get("position", 0),
                "playedGames": row.get("playedGames", 0),
                "won": row.get("won", 0),
                "draw": row.get("draw", 0),
                "lost": row.get("lost", 0),
                "goalsFor": row.get("goalsFor", 0),
                "goalsAgainst": row.get("goalsAgainst", 0),
                "points": row.get("points", 0),
                "form": row.get("form", "")
            }
    return None


def get_standings_bundle(team_id, competition_id, season_year):
    data = api_get(
        f"competitions/{competition_id}/standings",
        params={"season": season_year},
        cache_key=f"standings_{competition_id}_{season_year}",
        ttl=3600
    )

    if not data or not isinstance(data, dict) or "_error" in data:
        return {"TOTAL": None, "HOME": None, "AWAY": None}

    result = {"TOTAL": None, "HOME": None, "AWAY": None}
    for standing in data.get("standings", []):
        standing_type = standing.get("type")
        if standing_type in result:
            result[standing_type] = find_team_row(standing.get("table", []), team_id)

    return result


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/matches")
def api_matches(date: str = Query(None)):
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    collected = []
    found = []

    for code in DEFAULT_COMPETITIONS:
        data = api_get(
            f"competitions/{code}/matches",
            params={"dateFrom": date, "dateTo": date},
            cache_key=f"matches_{code}_{date}",
            ttl=1800
        )

        if data and isinstance(data, dict) and "_error" not in data and data.get("matches"):
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
    logger.info(f"=== ANALYZE match_id={match_id}, home={home_id}, away={away_id}, comp={competition_id} ===")
    
    match_detail = api_get(
        f"matches/{match_id}",
        cache_key=f"match_detail_{match_id}",
        ttl=3600
    )

    if match_detail and isinstance(match_detail, dict) and "_error" not in match_detail:
        home_team = safe_get(match_detail, "homeTeam", "name", default=home_team)
        away_team = safe_get(match_detail, "awayTeam", "name", default=away_team)
        home_short = safe_get(match_detail, "homeTeam", "shortName", default=home_short)
        away_short = safe_get(match_detail, "awayTeam", "shortName", default=away_short)
        home_logo = safe_get(match_detail, "homeTeam", "crest", default=home_logo)
        away_logo = safe_get(match_detail, "awayTeam", "crest", default=away_logo)
        league = safe_get(match_detail, "competition", "name", default=league)
        country = safe_get(match_detail, "area", "name", default=country) or safe_get(match_detail, "competition", "area", "name", default=country)
        venue = match_detail.get("venue", venue)
        status = match_detail.get("status", status)
        matchday = match_detail.get("matchday", matchday)
        if not date:
            date = (match_detail.get("utcDate") or "")[:10]
        if time == "--:--":
            time = (match_detail.get("utcDate") or "")[11:16]
        if home_score == "":
            home_score = safe_get(match_detail, "score", "fullTime", "home", default="")
        if away_score == "":
            away_score = safe_get(match_detail, "score", "fullTime", "away", default="")

    season_year = datetime.utcnow().year
    if match_detail and isinstance(match_detail, dict) and "_error" not in match_detail:
        season_start = safe_get(match_detail, "season", "startDate", default="")
        if isinstance(season_start, str) and len(season_start) >= 4:
            season_year = int(season_start[:4])
    
    logger.info(f"Season year: {season_year}")

    # === SOLO STANDINGS: 1 llamada a la API ===
    home_bundle = get_standings_bundle(home_id, competition_id, season_year)
    away_bundle = get_standings_bundle(away_id, competition_id, season_year)

    # Extraer stats desde standings
    home_total = home_bundle.get("TOTAL")
    away_total = away_bundle.get("TOTAL")
    
    home_stats = extract_stats_from_standings(home_total, home_total.get("form", "") if home_total else "")
    away_stats = extract_stats_from_standings(away_total, away_total.get("form", "") if away_total else "")
    
    # Fallback si no hay standings
    if not home_stats:
        home_stats = {
            "played": 0, "won": 0, "draw": 0, "lost": 0,
            "goals_for": 0, "goals_against": 0,
            "avg_total_goals": 0, "avg_team_goals": 0, "avg_conceded": 0,
            "btts_pct": 0, "over_1_5_pct": 0, "over_2_5_pct": 0, "over_3_5_pct": 0,
            "clean_sheet_pct": 0, "failed_to_score_pct": 0,
            "form_string": "", "form": [], "points": 0, "position": 0
        }
    
    if not away_stats:
        away_stats = dict(home_stats)
    
    home_mode = "STANDINGS_TOTAL"
    away_mode = "STANDINGS_TOTAL"

    home_table = home_total or {"position": 0, "points": 0, "won": 0, "draw": 0, "lost": 0, "goals_for": 0, "goals_against": 0}
    away_table = away_total or {"position": 0, "points": 0, "won": 0, "draw": 0, "lost": 0, "goals_for": 0, "goals_against": 0}

    # H2H (opcional, cacheada)
    h2h_data = api_get(
        f"matches/{match_id}/head2head",
        params={"limit": 5},
        cache_key=f"h2h_{match_id}",
        ttl=3600
    )

    h2h_matches = []
    h2h_stats = {
        "home_wins": 0, "away_wins": 0, "draws": 0,
        "home_goals": 0, "away_goals": 0, "total_matches": 0
    }

    if h2h_data and isinstance(h2h_data, dict) and "_error" not in h2h_data and h2h_data.get("aggregates"):
        agg = h2h_data["aggregates"]
        h2h_stats = {
            "home_wins": safe_get(agg, "homeTeam", "wins", default=0),
            "away_wins": safe_get(agg, "awayTeam", "wins", default=0),
            "draws": safe_get(agg, "homeTeam", "draws", default=0),
            "home_goals": safe_get(agg, "homeTeam", "goals", default=0),
            "away_goals": safe_get(agg, "awayTeam", "goals", default=0),
            "total_matches": agg.get("numberOfMatches", 0)
        }

        for m in h2h_data.get("matches", [])[:5]:
            h2h_matches.append({
                "date": (m.get("utcDate") or "")[:10],
                "home": safe_get(m, "homeTeam", "name", default=""),
                "away": safe_get(m, "awayTeam", "name", default=""),
                "homeScore": safe_get(m, "score", "fullTime", "home", default=None),
                "awayScore": safe_get(m, "score", "fullTime", "away", default=None),
                "competition": safe_get(m, "competition", "name", default="")
            })

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
            "minute": safe_get(match_detail or {}, "minute", default=0),
            "matchday": matchday,
            "home_score": parse_score_value(home_score),
            "away_score": parse_score_value(away_score),
            "halfTimeHome": safe_get(match_detail or {}, "score", "halfTime", "home", default=None),
            "halfTimeAway": safe_get(match_detail or {}, "score", "halfTime", "away", default=None)
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
        "probabilities": probabilities,
        "odds": {
            "home": safe_get(match_detail or {}, "odds", "homeWin", default=0),
            "draw": safe_get(match_detail or {}, "odds", "draw", default=0),
            "away": safe_get(match_detail or {}, "odds", "awayWin", default=0)
        },
        "stats_available": bool(home_stats["played"] or away_stats["played"]),
        "debug": {
            "match_id": match_id,
            "home_id": home_id,
            "away_id": away_id,
            "competition_id": competition_id,
            "season_year_used": season_year,
            "home_mode_used": home_mode,
            "away_mode_used": away_mode,
            "home_stats_played": home_stats["played"],
            "away_stats_played": away_stats["played"],
            "home_total_found": bool(home_bundle["TOTAL"]),
            "away_total_found": bool(away_bundle["TOTAL"])
        }
    })


@app.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "cache_size": len(CACHE),
        "api_key": "configured" if API_KEY else "missing",
        "rate_limit_until": RATE_LIMIT_UNTIL.isoformat() if RATE_LIMIT_UNTIL else None,
        "version": "5.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
