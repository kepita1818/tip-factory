import os
import logging
from datetime import datetime, timedelta

import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TipFactory", version="10.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

API_KEY = os.environ.get("API_FOOTBALL_KEY", "").strip()
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY} if API_KEY else {}

CACHE = {}


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
            return cached

    if not API_KEY:
        logger.error("API_FOOTBALL_KEY missing")
        return None

    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)

        if resp.status_code == 429:
            logger.error("RATE LIMIT")
            return None
        if resp.status_code in (401, 403):
            logger.error(f"AUTH ERROR {resp.status_code}")
            return None
        if resp.status_code == 404:
            logger.error(f"NOT FOUND {endpoint}")
            return None

        resp.raise_for_status()
        data = resp.json()

        if cache_key:
            cache_set(cache_key, data)

        return data
    except Exception as e:
        logger.error(f"API error in {endpoint}: {e}")
        return None


def safe_get(d, *keys, default=None):
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def format_match(m):
    home = m.get("homeTeam", {}) or {}
    away = m.get("awayTeam", {}) or {}
    competition = m.get("competition", {}) or {}
    area = m.get("area", {}) or competition.get("area", {}) or {}
    score = m.get("score", {}) or {}
    ft = score.get("fullTime", {}) if isinstance(score, dict) else {}
    ht = score.get("halfTime", {}) if isinstance(score, dict) else {}

    match_date = (m.get("utcDate") or "")[:10]

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
        "matchDate": match_date,
        "status": status_map.get(status, status),
        "statusText": status,
        "minute": 0,
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


def build_form_and_stats(team_id, matches, standings=None):
    played = won = draw = lost = 0
    gf = ga = 0
    over15 = over25 = over35 = btts = clean_sheet = failed_to_score = 0
    form = []

    for m in matches:
        home = m.get("homeTeam", {}) or {}
        away = m.get("awayTeam", {}) or {}
        score = safe_get(m, "score", "fullTime", default={}) or {}

        hg = score.get("home")
        ag = score.get("away")
        if hg is None or ag is None:
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

    stats = {
        "position": standings.get("position", 0) if standings else 0,
        "played": standings.get("played", played) if standings else played,
        "won": standings.get("won", won) if standings else won,
        "draw": standings.get("draw", draw) if standings else draw,
        "lost": standings.get("lost", lost) if standings else lost,
        "goals_for": standings.get("goals_for", gf) if standings else gf,
        "goals_against": standings.get("goals_against", ga) if standings else ga,
        "points": standings.get("points", won * 3 + draw) if standings else (won * 3 + draw),
        "form_string": standings.get("form", "".join([x["result"] for x in form])) if standings else "".join([x["result"] for x in form]),
        "avg_total_goals": round((gf + ga) / played, 2) if played else 0,
        "avg_team_goals": round(gf / played, 2) if played else 0,
        "avg_conceded": round(ga / played, 2) if played else 0,
        "btts_pct": round((btts / played) * 100, 1) if played else 0,
        "over_1_5_pct": round((over15 / played) * 100, 1) if played else 0,
        "over_2_5_pct": round((over25 / played) * 100, 1) if played else 0,
        "over_3_5_pct": round((over35 / played) * 100, 1) if played else 0,
        "clean_sheet_pct": round((clean_sheet / played) * 100, 1) if played else 0,
        "failed_to_score_pct": round((failed_to_score / played) * 100, 1) if played else 0
    }

    return form, stats


def get_team_recent_matches(team_id, competition_id, limit=10):
    if not team_id:
        return []

    params = {
        "status": "FINISHED",
        "limit": limit
    }

    if competition_id:
        params["competitions"] = str(competition_id)

    data = api_get(
        f"teams/{team_id}/matches",
        params=params,
        cache_key=f"team_matches_{team_id}_{competition_id}_{limit}",
        ttl=1800
    )

    matches = data.get("matches", []) if isinstance(data, dict) else []

    if not matches:
        data = api_get(
            f"teams/{team_id}/matches",
            params={"status": "FINISHED", "limit": limit},
            cache_key=f"team_matches_fallback_{team_id}_{limit}",
            ttl=1800
        )
        matches = data.get("matches", []) if isinstance(data, dict) else []

    return matches


def get_team_standings(team_id, competition_id, season_year):
    if not team_id or not competition_id:
        return None

    data = api_get(
        f"competitions/{competition_id}/standings",
        params={"season": season_year},
        cache_key=f"standings_{competition_id}_{season_year}",
        ttl=3600
    )

    if not data or not data.get("standings"):
        return None

    for standing in data.get("standings", []):
        for row in standing.get("table", []):
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


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/matches")
def matches(date: str = Query(None)):
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    logger.info(f"BUSCANDO PARTIDOS PARA: {date}")

    data = api_get(
        "matches",
        params={"dateFrom": date, "dateTo": date},
        cache_key=f"matches_{date}",
        ttl=300
    )

    matches = []
    if data and data.get("matches"):
        matches = [format_match(m) for m in data["matches"]]
        matches = [m for m in matches if m["matchDate"] == date]

    if matches:
        return {
            "matches": matches,
            "requested_date": date,
            "source_date": date,
            "is_exact": True,
            "source": "football-data.org"
        }

    for delta in [-1, 1, -2, 2, -3, 3]:
        check_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
        data = api_get(
            "matches",
            params={"dateFrom": check_date, "dateTo": check_date},
            cache_key=f"matches_{check_date}",
            ttl=300
        )

        alt_matches = []
        if data and data.get("matches"):
            alt_matches = [format_match(m) for m in data["matches"]]
            alt_matches = [m for m in alt_matches if m["matchDate"] == check_date]

        if alt_matches:
            return {
                "matches": alt_matches,
                "requested_date": date,
                "source_date": check_date,
                "is_exact": False,
                "source": "football-data.org"
            }

    return {
        "matches": [],
        "requested_date": date,
        "source_date": None,
        "is_exact": True,
        "source": "football-data.org"
    }


@app.get("/api/analyze/{match_id}")
def analyze(match_id: int):
    logger.info(f"ANALIZANDO PARTIDO {match_id}")

    match = api_get(f"matches/{match_id}", cache_key=f"match_{match_id}", ttl=300)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    match_info = format_match(match)

    home_id = safe_get(match, "homeTeam", "id", default=None)
    away_id = safe_get(match, "awayTeam", "id", default=None)
    competition_id = safe_get(match, "competition", "id", default=None)

    season = match.get("season", {}) or {}
    season_year = int((season.get("startDate") or "2025-01-01")[:4])

    home_recent = get_team_recent_matches(home_id, competition_id, 10)
    away_recent = get_team_recent_matches(away_id, competition_id, 10)

    home_standings = get_team_standings(home_id, competition_id, season_year)
    away_standings = get_team_standings(away_id, competition_id, season_year)

    home_form, home_stats = build_form_and_stats(home_id, home_recent, home_standings)
    away_form, away_stats = build_form_and_stats(away_id, away_recent, away_standings)

    h2h_data = api_get(
        f"matches/{match_id}/head2head",
        params={"limit": 10},
        cache_key=f"h2h_{match_id}",
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
            "home_team": safe_get(match, "homeTeam", "name", default="Local"),
            "away_team": safe_get(match, "awayTeam", "name", default="Visitante"),
            "home_short": safe_get(match, "homeTeam", "shortName", default="Local"),
            "away_short": safe_get(match, "awayTeam", "shortName", default="Visitante"),
            "home_logo": safe_get(match, "homeTeam", "crest", default=""),
            "away_logo": safe_get(match, "awayTeam", "crest", default=""),
            "league": safe_get(match, "competition", "name", default=""),
            "country": safe_get(match, "area", "name", default="") or safe_get(match, "competition", "area", "name", default=""),
            "date": (match.get("utcDate") or "")[:10],
            "time": (match.get("utcDate") or "")[11:16],
            "venue": match.get("venue", ""),
            "status": match.get("status", "SCHEDULED"),
            "minute": 0,
            "matchday": match.get("matchday", 0),
            "home_score": match_info.get("homeScore"),
            "away_score": match_info.get("awayScore"),
            "halfTimeHome": match_info.get("halfTimeHome"),
            "halfTimeAway": match_info.get("halfTimeAway")
        },
        "home_form": home_form,
        "away_form": away_form,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "h2h": {
            "matches": h2h_matches,
            "stats": h2h_stats
        },
        "probabilities": probabilities,
        "odds": {
            "home": 0,
            "draw": 0,
            "away": 0
        },
        "stats_available": bool(home_stats["played"] or away_stats["played"]),
        "debug": {
            "match_id": match_id,
            "competition": {
                "id": competition_id,
                "code": safe_get(match, "competition", "code", default=""),
                "name": safe_get(match, "competition", "name", default="")
            },
            "home_id": home_id,
            "away_id": away_id,
            "home_recent_count": len(home_recent),
            "away_recent_count": len(away_recent),
            "home_recent_raw": [
                {
                    "date": (m.get("utcDate") or "")[:10],
                    "home": safe_get(m, "homeTeam", "name", default=""),
                    "away": safe_get(m, "awayTeam", "name", default=""),
                    "homeScore": safe_get(m, "score", "fullTime", "home", default=None),
                    "awayScore": safe_get(m, "score", "fullTime", "away", default=None),
                    "competition": safe_get(m, "competition", "name", default="")
                }
                for m in home_recent[:10]
            ],
            "away_recent_raw": [
                {
                    "date": (m.get("utcDate") or "")[:10],
                    "home": safe_get(m, "homeTeam", "name", default=""),
                    "away": safe_get(m, "awayTeam", "name", default=""),
                    "homeScore": safe_get(m, "score", "fullTime", "home", default=None),
                    "awayScore": safe_get(m, "score", "fullTime", "away", default=None),
                    "competition": safe_get(m, "competition", "name", default="")
                }
                for m in away_recent[:10]
            ]
        }
    })


@app.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "cache_size": len(CACHE),
        "api_key": "configured" if API_KEY else "missing",
        "version": "10.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
