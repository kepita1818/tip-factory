import os
import logging
from datetime import datetime

import requests
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="TipFactory", version="2.5.0")

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


def cache_get(key, ttl=300):
    if key in CACHE:
        data, ts = CACHE[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None


def cache_set(key, data):
    CACHE[key] = (data, datetime.now())


def api_get(endpoint, params=None, cache_key=None, ttl=300):
    if cache_key:
        cached = cache_get(cache_key, ttl)
        if cached is not None:
            logger.info(f"CACHE HIT: {cache_key}")
            return cached

    if not API_KEY:
        logger.error("API_FOOTBALL_KEY missing")
        return None

    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        logger.info(f"API CALL: {url} | params={params}")
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)

        if resp.status_code == 404:
            logger.warning(f"NOT FOUND {endpoint} {params}")
            return None
        if resp.status_code in (401, 403, 402):
            logger.error(f"AUTH/PAYMENT ERROR {resp.status_code} on {endpoint} - {resp.text[:200]}")
            return None
        if resp.status_code == 429:
            logger.error(f"RATE LIMIT on {endpoint}")
            return None

        resp.raise_for_status()
        data = resp.json()
        logger.info(f"API SUCCESS: {endpoint} -> {len(str(data))} chars")

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


def extract_season_year(match_detail, competition_id):
    season_from_match = safe_get(match_detail or {}, "season", "startDate", default="")
    if isinstance(season_from_match, str) and len(season_from_match) >= 4:
        return int(season_from_match[:4])

    comp_data = api_get(
        f"competitions/{competition_id}",
        cache_key=f"competition_{competition_id}",
        ttl=3600
    )

    start_date = safe_get(comp_data or {}, "currentSeason", "startDate", default="")
    if isinstance(start_date, str) and len(start_date) >= 4:
        return int(start_date[:4])

    return datetime.utcnow().year


def get_team_matches(team_id, competition_id, season_year, venue=None, limit=50):
    """
    Obtiene partidos FINISHED de un equipo. 
    Estrategia: primero intenta con filtro de competición, si falla o está vacío,
    intenta sin filtro de competición (todos los partidos del equipo esa temporada).
    """
    all_matches = []
    
    # Intento 1: Con filtro de competición (como string, la API acepta IDs numéricos)
    params_comp = {
        "season": season_year,
        "competitions": str(competition_id),
        "status": "FINISHED",
        "limit": limit
    }
    if venue:
        params_comp["venue"] = venue

    data_comp = api_get(
        f"teams/{team_id}/matches",
        params=params_comp,
        cache_key=f"team_matches_comp_{team_id}_{competition_id}_{season_year}_{venue}_{limit}",
        ttl=1800
    )
    
    matches_comp = data_comp.get("matches", []) if isinstance(data_comp, dict) else []
    logger.info(f"Team {team_id} matches WITH comp filter: {len(matches_comp)} found")
    
    if len(matches_comp) >= 3:
        return matches_comp
    
    # Intento 2: Sin filtro de competición (puede que el plan gratuito no permita filtrar por comp)
    params_all = {
        "season": season_year,
        "status": "FINISHED",
        "limit": limit
    }
    if venue:
        params_all["venue"] = venue

    data_all = api_get(
        f"teams/{team_id}/matches",
        params=params_all,
        cache_key=f"team_matches_all_{team_id}_{season_year}_{venue}_{limit}",
        ttl=1800
    )
    
    matches_all = data_all.get("matches", []) if isinstance(data_all, dict) else []
    logger.info(f"Team {team_id} matches WITHOUT comp filter: {len(matches_all)} found")
    
    # Filtrar manualmente por competición si es necesario
    if matches_all and competition_id:
        filtered = [m for m in matches_all if safe_get(m, "competition", "id") == competition_id]
        if len(filtered) >= 3:
            logger.info(f"After manual filter: {len(filtered)} matches")
            return filtered
        # Si no hay suficientes filtrados, devolver todos (mejor tener datos de otra comp que nada)
        if matches_all:
            return matches_all
    
    # Fallback final: devolver lo que sea que tengamos
    if matches_comp:
        return matches_comp
    if matches_all:
        return matches_all
    return []


def extract_team_view(team_id, matches):
    played = won = draw = lost = 0
    gf = ga = 0
    over15 = over25 = over35 = btts = clean_sheet = failed_to_score = 0
    form = []

    for m in matches[:10]:
        home = m.get("homeTeam", {}) or {}
        away = m.get("awayTeam", {}) or {}
        full = safe_get(m, "score", "fullTime", default={}) or {}

        # La API v4 usa 'home' y 'away' directamente en fullTime
        hg = full.get("home")
        ag = full.get("away")

        if hg is None or ag is None:
            logger.warning(f"Skipping match {m.get('id')} - no score data: home={hg}, away={ag}")
            continue

        is_home = home.get("id") == team_id
        is_away = away.get("id") == team_id
        if not is_home and not is_away:
            continue

        tg = hg if is_home else ag
        og = ag if is_home else hg

        played += 1
        gf += tg
        ga += og

        if tg > og:
            result = "W"
            won += 1
        elif tg == og:
            result = "D"
            draw += 1
        else:
            result = "L"
            lost += 1

        total = tg + og
        if total > 1:
            over15 += 1
        if total > 2:
            over25 += 1
        if total > 3:
            over35 += 1
        if tg > 0 and og > 0:
            btts += 1
        if og == 0:
            clean_sheet += 1
        if tg == 0:
            failed_to_score += 1

        if len(form) < 5:
            form.append({
                "result": result,
                "result_text": "Victoria" if result == "W" else "Empate" if result == "D" else "Derrota",
                "team_goals": tg,
                "opp_goals": og,
                "opponent": away.get("name", "Rival") if is_home else home.get("name", "Rival"),
                "venue": "home" if is_home else "away",
                "date": (m.get("utcDate") or "")[:10],
                "competition": safe_get(m, "competition", "name", default="")
            })

    result = {
        "played": played,
        "won": won,
        "draw": draw,
        "lost": lost,
        "goals_for": gf,
        "goals_against": ga,
        "avg_total_goals": round((gf + ga) / played, 2) if played else 0,
        "avg_team_goals": round(gf / played, 2) if played else 0,
        "avg_conceded": round(ga / played, 2) if played else 0,
        "btts_pct": round((btts / played) * 100, 1) if played else 0,
        "over_1_5_pct": round((over15 / played) * 100, 1) if played else 0,
        "over_2_5_pct": round((over25 / played) * 100, 1) if played else 0,
        "over_3_5_pct": round((over35 / played) * 100, 1) if played else 0,
        "clean_sheet_pct": round((clean_sheet / played) * 100, 1) if played else 0,
        "failed_to_score_pct": round((failed_to_score / played) * 100, 1) if played else 0,
        "form_string": "".join([x["result"] for x in form]),
        "form": form
    }
    
    logger.info(f"Team {team_id} stats: played={played}, GF={gf}, GA={ga}, form={result['form_string']}")
    return result


def find_team_row(table_rows, team_id):
    for row in table_rows:
        if safe_get(row, "team", "id") == team_id:
            return {
                "position": row.get("position", 0),
                "played": row.get("playedGames", 0),
                "won": row.get("won", 0),
                "draw": row.get("draw", 0),
                "lost": row.get("lost", 0),
                "goals_for": row.get("goalsFor", 0),
                "goals_against": row.get("goalsAgainst", 0),
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

    result = {"TOTAL": None, "HOME": None, "AWAY": None}
    if not data or not data.get("standings"):
        return result

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
            ttl=300
        )

        if data and data.get("matches"):
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
    logger.info(f"ANALYZE match_id={match_id}, home_id={home_id}, away_id={away_id}, comp_id={competition_id}")
    
    match_detail = api_get(
        f"matches/{match_id}",
        cache_key=f"match_detail_{match_id}",
        ttl=1800
    )

    if match_detail:
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

    season_year = extract_season_year(match_detail, competition_id)
    logger.info(f"Using season year: {season_year}")

    # Obtener partidos recientes
    home_recent_home = get_team_matches(home_id, competition_id, season_year, venue="HOME", limit=50)
    away_recent_away = get_team_matches(away_id, competition_id, season_year, venue="AWAY", limit=50)
    home_recent_all = get_team_matches(home_id, competition_id, season_year, venue=None, limit=50)
    away_recent_all = get_team_matches(away_id, competition_id, season_year, venue=None, limit=50)

    # Decidir qué datos usar para stats
    if len(home_recent_home) >= 3:
        home_stats = extract_team_view(home_id, home_recent_home)
        home_mode = "HOME"
    else:
        home_stats = extract_team_view(home_id, home_recent_all)
        home_mode = "ALL"

    if len(away_recent_away) >= 3:
        away_stats = extract_team_view(away_id, away_recent_away)
        away_mode = "AWAY"
    else:
        away_stats = extract_team_view(away_id, away_recent_all)
        away_mode = "ALL"

    home_bundle = get_standings_bundle(home_id, competition_id, season_year)
    away_bundle = get_standings_bundle(away_id, competition_id, season_year)

    home_table = home_bundle["TOTAL"] or {"position": 0, "points": 0, "won": 0, "draw": 0, "lost": 0, "goals_for": 0, "goals_against": 0}
    away_table = away_bundle["TOTAL"] or {"position": 0, "points": 0, "won": 0, "draw": 0, "lost": 0, "goals_for": 0, "goals_against": 0}

    h2h_data = api_get(
        f"matches/{match_id}/head2head",
        params={"limit": 5, "competitions": str(competition_id)},
        cache_key=f"h2h_{match_id}_{competition_id}",
        ttl=3600
    )

    h2h_matches = []
    h2h_stats = {
        "home_wins": 0,
        "away_wins": 0,
        "draws": 0,
        "home_goals": 0,
        "away_goals": 0,
        "total_matches": 0
    }

    if h2h_data and h2h_data.get("aggregates"):
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
            "home_recent_home_count": len(home_recent_home),
            "away_recent_away_count": len(away_recent_away),
            "home_recent_all_count": len(home_recent_all),
            "away_recent_all_count": len(away_recent_all),
            "home_mode_used": home_mode,
            "away_mode_used": away_mode,
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
        "version": "2.5.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
