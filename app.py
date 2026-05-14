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

app = FastAPI(title="TipFactory", version="4.0.0")

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
HEADERS = {"X-Auth-Token": API_KEY}

CACHE = {}

TOP_COMPETITIONS = ["PL", "PD", "SA", "BL1", "FL1", "PPL", "DED", "ELC", "BSA", "CL", "EL"]


def cache_get(key, ttl=300):
    if key in CACHE:
        data, ts = CACHE[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None


def cache_set(key, data):
    CACHE[key] = (data, datetime.now())


def api_request(endpoint, params=None, cache_key=None, ttl=300):
    if cache_key:
        cached = cache_get(cache_key, ttl)
        if cached is not None:
            return cached

    if not API_KEY:
        logger.error("API_FOOTBALL_KEY missing")
        return None

    try:
        url = f"{BASE_URL}/{endpoint}"
        response = requests.get(url, headers=HEADERS, params=params, timeout=20)

        if response.status_code == 404:
            logger.warning(f"404 {endpoint}")
            return None
        if response.status_code in (401, 403):
            logger.error(f"Auth error {response.status_code} {endpoint}")
            return None
        if response.status_code == 429:
            logger.error(f"Rate limit {endpoint}")
            return None

        response.raise_for_status()
        data = response.json()

        if cache_key:
            cache_set(cache_key, data)

        return data
    except Exception as e:
        logger.error(f"API error {endpoint}: {e}")
        return None


def format_match(m):
    home = m.get("homeTeam", {}) or {}
    away = m.get("awayTeam", {}) or {}
    comp = m.get("competition", {}) or {}
    area = m.get("area", {}) or comp.get("area", {}) or {}
    score = m.get("score", {}) or {}
    ft = score.get("fullTime", {}) or {}
    ht = score.get("halfTime", {}) or {}

    return {
        "id": m.get("id"),
        "utcDate": m.get("utcDate", ""),
        "matchDate": (m.get("utcDate", "")[:10] if m.get("utcDate") else ""),
        "status": m.get("status", "SCHEDULED"),
        "venue": m.get("venue", "") or "",
        "matchday": m.get("matchday", 0) or 0,
        "homeTeam": {
            "id": home.get("id"),
            "name": home.get("name", "Local"),
            "shortName": home.get("shortName") or home.get("tla") or home.get("name", "Local")[:15],
            "crest": home.get("crest", "") or ""
        },
        "awayTeam": {
            "id": away.get("id"),
            "name": away.get("name", "Visitante"),
            "shortName": away.get("shortName") or away.get("tla") or away.get("name", "Visitante")[:15],
            "crest": away.get("crest", "") or ""
        },
        "competition": {
            "id": comp.get("id"),
            "name": comp.get("name", ""),
            "code": comp.get("code", "")
        },
        "league_name": comp.get("name", ""),
        "country": area.get("name", ""),
        "homeScore": ft.get("home"),
        "awayScore": ft.get("away"),
        "halfTimeHome": ht.get("home"),
        "halfTimeAway": ht.get("away")
    }


def fetch_matches_for_date(date_str):
    matches = []

    general = api_request(
        "matches",
        {"dateFrom": date_str, "dateTo": date_str},
        cache_key=f"matches_{date_str}",
        ttl=300
    )

    if general and general.get("matches"):
        matches.extend([format_match(x) for x in general["matches"]])

    if not matches:
        for code in TOP_COMPETITIONS:
            comp = api_request(
                f"competitions/{code}/matches",
                {"dateFrom": date_str, "dateTo": date_str},
                cache_key=f"comp_{code}_{date_str}",
                ttl=600
            )
            if comp and comp.get("matches"):
                matches.extend([format_match(x) for x in comp["matches"]])

    deduped = []
    seen = set()
    for m in matches:
        mid = m.get("id")
        if mid and mid not in seen and m.get("matchDate") == date_str:
            seen.add(mid)
            deduped.append(m)

    return deduped


def find_team_id(name):
    if not name:
        return None

    data = api_request("teams", cache_key="all_teams", ttl=86400)
    if not data or not data.get("teams"):
        return None

    target = name.strip().lower()

    for t in data["teams"]:
        candidates = [
            (t.get("name") or "").lower(),
            (t.get("shortName") or "").lower(),
            (t.get("tla") or "").lower()
        ]
        if target in candidates:
            return t.get("id")

    for t in data["teams"]:
        candidates = [
            (t.get("name") or "").lower(),
            (t.get("shortName") or "").lower()
        ]
        if any(target in c or c in target for c in candidates if c):
            return t.get("id")

    return None


def get_recent_team_matches(team_id, limit=10):
    if not team_id:
        return []

    data = api_request(
        f"teams/{team_id}/matches",
        {"status": "FINISHED", "limit": limit},
        cache_key=f"team_recent_{team_id}_{limit}",
        ttl=1800
    )

    if not data or not data.get("matches"):
        return []

    return data["matches"]


def build_stats(team_id, matches):
    played = won = draw = lost = 0
    gf = ga = 0
    over15 = over25 = over35 = btts = cs = fts = 0
    form = []

    for m in matches:
        home = m.get("homeTeam", {}) or {}
        away = m.get("awayTeam", {}) or {}
        score = (m.get("score", {}) or {}).get("fullTime", {}) or {}
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
            cs += 1
        if tg == 0:
            fts += 1

        if len(form) < 5:
            form.append({
                "result": result,
                "team_goals": tg,
                "opp_goals": og,
                "date": (m.get("utcDate") or "")[:10]
            })

    if played == 0:
        return [], {
            "position": 0,
            "played": 0,
            "won": 0,
            "draw": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
            "form_string": "",
            "avg_total_goals": 0,
            "avg_team_goals": 0,
            "avg_conceded": 0,
            "btts_pct": 0,
            "over_1_5_pct": 0,
            "over_2_5_pct": 0,
            "over_3_5_pct": 0,
            "clean_sheet_pct": 0,
            "failed_to_score_pct": 0
        }

    return form, {
        "position": 0,
        "played": played,
        "won": won,
        "draw": draw,
        "lost": lost,
        "goals_for": gf,
        "goals_against": ga,
        "points": won * 3 + draw,
        "form_string": "",
        "avg_total_goals": round((gf + ga) / played, 2),
        "avg_team_goals": round(gf / played, 2),
        "avg_conceded": round(ga / played, 2),
        "btts_pct": round((btts / played) * 100, 1),
        "over_1_5_pct": round((over15 / played) * 100, 1),
        "over_2_5_pct": round((over25 / played) * 100, 1),
        "over_3_5_pct": round((over35 / played) * 100, 1),
        "clean_sheet_pct": round((cs / played) * 100, 1),
        "failed_to_score_pct": round((fts / played) * 100, 1)
    }


def get_standings(team_id, competition_id, season_year):
    if not team_id or not competition_id:
        return None

    data = api_request(
        f"competitions/{competition_id}/standings",
        {"season": season_year},
        cache_key=f"standings_{competition_id}_{season_year}",
        ttl=3600
    )

    if not data or not data.get("standings"):
        return None

    for standing in data["standings"]:
        for row in standing.get("table", []):
            if row.get("team", {}).get("id") == team_id:
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

    exact = fetch_matches_for_date(date)
    if exact:
        return {"matches": exact, "requested_date": date, "source_date": date, "is_exact": True}

    for delta in [-1, 1, -2, 2, -3, 3]:
        alt = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
        alt_matches = fetch_matches_for_date(alt)
        if alt_matches:
            return {"matches": alt_matches, "requested_date": date, "source_date": alt, "is_exact": False}

    return {"matches": [], "requested_date": date, "source_date": None, "is_exact": True}


@app.get("/api/analyze/{match_id}")
def analyze(
    match_id: int,
    home_team: str = Query("Local"),
    away_team: str = Query("Visitante"),
    home_logo: str = Query(""),
    away_logo: str = Query(""),
    league: str = Query(""),
    date: str = Query(""),
    time: str = Query("--:--"),
    country: str = Query("")
):
    match = api_request(f"matches/{match_id}", cache_key=f"match_{match_id}", ttl=300)

    home_id = None
    away_id = None
    competition_id = None
    season_year = datetime.utcnow().year

    match_info = {
        "home_team": home_team,
        "away_team": away_team,
        "home_short": home_team[:12],
        "away_short": away_team[:12],
        "home_logo": home_logo,
        "away_logo": away_logo,
        "league": league,
        "country": country,
        "date": date,
        "time": time,
        "venue": "",
        "status": "SCHEDULED",
        "minute": 0,
        "matchday": 0,
        "home_score": None,
        "away_score": None,
        "halfTimeHome": None,
        "halfTimeAway": None
    }

    if match:
        fm = format_match(match)
        match_info = {
            "home_team": fm["homeTeam"]["name"],
            "away_team": fm["awayTeam"]["name"],
            "home_short": fm["homeTeam"]["shortName"],
            "away_short": fm["awayTeam"]["shortName"],
            "home_logo": fm["homeTeam"]["crest"],
            "away_logo": fm["awayTeam"]["crest"],
            "league": fm["league_name"],
            "country": fm["country"],
            "date": fm["matchDate"],
            "time": (fm["utcDate"][11:16] if fm["utcDate"] else time),
            "venue": fm["venue"],
            "status": fm["status"],
            "minute": 0,
            "matchday": fm["matchday"],
            "home_score": fm["homeScore"],
            "away_score": fm["awayScore"],
            "halfTimeHome": fm["halfTimeHome"],
            "halfTimeAway": fm["halfTimeAway"]
        }

        home_id = fm["homeTeam"]["id"]
        away_id = fm["awayTeam"]["id"]
        competition_id = fm["competition"]["id"]
        if match.get("season", {}).get("startDate"):
            season_year = int(match["season"]["startDate"][:4])

    if not home_id:
        home_id = find_team_id(home_team)
    if not away_id:
        away_id = find_team_id(away_team)

    home_recent = get_recent_team_matches(home_id, 10)
    away_recent = get_recent_team_matches(away_id, 10)

    home_form, home_stats = build_stats(home_id, home_recent)
    away_form, away_stats = build_stats(away_id, away_recent)

    home_st = get_standings(home_id, competition_id, season_year)
    away_st = get_standings(away_id, competition_id, season_year)

    if home_st:
        home_stats["position"] = home_st["position"]
        home_stats["played"] = home_st["played"]
        home_stats["won"] = home_st["won"]
        home_stats["draw"] = home_st["draw"]
        home_stats["lost"] = home_st["lost"]
        home_stats["goals_for"] = home_st["goals_for"]
        home_stats["goals_against"] = home_st["goals_against"]
        home_stats["points"] = home_st["points"]
        home_stats["form_string"] = home_st["form"]

    if away_st:
        away_stats["position"] = away_st["position"]
        away_stats["played"] = away_st["played"]
        away_stats["won"] = away_st["won"]
        away_stats["draw"] = away_st["draw"]
        away_stats["lost"] = away_st["lost"]
        away_stats["goals_for"] = away_st["goals_for"]
        away_stats["goals_against"] = away_st["goals_against"]
        away_stats["points"] = away_st["points"]
        away_stats["form_string"] = away_st["form"]

    probabilities = {
        "over_1_5": round((home_stats["over_1_5_pct"] + away_stats["over_1_5_pct"]) / 2, 1),
        "over_2_5": round((home_stats["over_2_5_pct"] + away_stats["over_2_5_pct"]) / 2, 1),
        "over_3_5": round((home_stats["over_3_5_pct"] + away_stats["over_3_5_pct"]) / 2, 1),
        "btts": round((home_stats["btts_pct"] + away_stats["btts_pct"]) / 2, 1),
        "total_expected_goals": round(home_stats["avg_team_goals"] + away_stats["avg_team_goals"], 2),
        "expected_corners": None,
        "expected_cards": None
    }

    debug = {
        "match_found": bool(match),
        "home_id": home_id,
        "away_id": away_id,
        "competition_id": competition_id,
        "season_year": season_year,
        "home_recent_count": len(home_recent),
        "away_recent_count": len(away_recent),
        "home_standings_found": bool(home_st),
        "away_standings_found": bool(away_st)
    }

    return JSONResponse({
        "match_info": match_info,
        "home_form": home_form,
        "away_form": away_form,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "h2h": {"matches": [], "stats": {}},
        "probabilities": probabilities,
        "odds": {"home": 0, "draw": 0, "away": 0},
        "stats_available": bool(home_stats["played"] or away_stats["played"]),
        "debug": debug
    })


@app.get("/health")
def health():
    return {
        "status": "ok",
        "cache_size": len(CACHE),
        "time": datetime.now().isoformat(),
        "api_key": "configured" if API_KEY else "missing",
        "version": "4.0.0"
    }
