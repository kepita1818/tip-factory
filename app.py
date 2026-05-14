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

app = FastAPI(title="TipFactory", version="1.1.0")

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
            return cached

    if not API_KEY:
        logger.error("API_FOOTBALL_KEY missing")
        return None

    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)

        if resp.status_code == 404:
            return None
        if resp.status_code in (401, 403):
            logger.error(f"AUTH ERROR {resp.status_code} on {endpoint}")
            return None
        if resp.status_code == 429:
            logger.error(f"RATE LIMIT on {endpoint}")
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


def build_stats(team_id, matches, standings=None):
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


def get_team_matches(team_id, competition_id=None, venue=None, limit=10):
    if not team_id:
        return []

    params = {
        "status": "FINISHED",
        "limit": limit
    }

    if competition_id:
        params["competitions"] = str(competition_id)

    if venue:
        params["venue"] = venue

    data = api_get(
        f"teams/{team_id}/matches",
        params=params,
        cache_key=f"tm_{team_id}_{competition_id}_{venue}_{limit}",
        ttl=1800
    )

    return data.get("matches", []) if isinstance(data, dict) else []


def get_standings(team_id, competition_id, season_year):
    if not team_id or not competition_id:
        return None

    data = api_get(
        f"competitions/{competition_id}/standings",
        params={"season": season_year},
        cache_key=f"st_{competition_id}_{season_year}",
        ttl=3600
    )
    if not data or not data.get("standings"):
        return None

    for standing in data["standings"]:
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
    season_year = datetime.utcnow().year

    home_recent = get_team_matches(home_id, competition_id, venue="HOME", limit=10)
    away_recent = get_team_matches(away_id, competition_id, venue="AWAY", limit=10)

    home_standings = get_standings(home_id, competition_id, season_year)
    away_standings = get_standings(away_id, competition_id, season_year)

    home_form, home_stats = build_stats(home_id, home_recent, home_standings)
    away_form, away_stats = build_stats(away_id, away_recent, away_standings)

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
            "minute": 0,
            "matchday": matchday,
            "home_score": None if home_score == "" else home_score,
            "away_score": None if away_score == "" else away_score,
            "halfTimeHome": None,
            "halfTimeAway": None
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
        "odds": {"home": 0, "draw": 0, "away": 0},
        "stats_available": bool(home_stats["played"] or away_stats["played"]),
        "debug": {
            "match_id": match_id,
            "home_id": home_id,
            "away_id": away_id,
            "competition_id": competition_id,
            "home_recent_count": len(home_recent),
            "away_recent_count": len(away_recent),
            "home_venue_filter": "HOME",
            "away_venue_filter": "AWAY"
        }
    })


@app.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "cache_size": len(CACHE),
        "api_key": "configured" if API_KEY else "missing",
        "version": "1.1.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
