import os
import logging
from datetime import datetime, timedelta

import requests
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
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

FOOTBALLDATA_IO_KEY = os.environ.get("FOOTBALLDATA_IO_KEY", "").strip()
FOOTBALL_DATA_ORG_KEY = os.environ.get("API_FOOTBALL_KEY", "").strip()

FDIO_BASE = "https://footballdata.io/api/v1"
FDORG_BASE = "https://api.football-data.org/v4"

FDIO_HEADERS = {"Authorization": f"Bearer {FOOTBALLDATA_IO_KEY}"} if FOOTBALLDATA_IO_KEY else {}
FDORG_HEADERS = {"X-Auth-Token": FOOTBALL_DATA_ORG_KEY} if FOOTBALL_DATA_ORG_KEY else {}

CACHE = {}


def cache_get(key, ttl=300):
    if key in CACHE:
        data, ts = CACHE[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None


def cache_set(key, data):
    CACHE[key] = (data, datetime.now())


def api_get(base_url, endpoint, headers=None, params=None, cache_key=None, ttl=300):
    if cache_key:
        cached = cache_get(cache_key, ttl)
        if cached is not None:
            return cached

    try:
        url = f"{base_url}/{endpoint.lstrip('/')}"
        resp = requests.get(url, headers=headers or {}, params=params, timeout=20)

        if resp.status_code in (401, 403):
            logger.error(f"AUTH ERROR {resp.status_code} {url}")
            return None
        if resp.status_code == 404:
            logger.warning(f"NOT FOUND {url}")
            return None
        if resp.status_code == 429:
            logger.error(f"RATE LIMIT {url}")
            return None

        resp.raise_for_status()
        data = resp.json()

        if cache_key:
            cache_set(cache_key, data)

        return data
    except Exception as e:
        logger.error(f"API error {base_url}/{endpoint}: {e}")
        return None


def fdio_request(endpoint, params=None, cache_key=None, ttl=300):
    if not FOOTBALLDATA_IO_KEY:
        return None
    return api_get(FDIO_BASE, endpoint, FDIO_HEADERS, params, cache_key, ttl)


def fdorg_request(endpoint, params=None, cache_key=None, ttl=300):
    if not FOOTBALL_DATA_ORG_KEY:
        return None
    return api_get(FDORG_BASE, endpoint, FDORG_HEADERS, params, cache_key, ttl)


def safe_get(d, *keys, default=None):
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def normalize_match(raw):
    home_name = safe_get(raw, "homeTeam", "name", default=None) or safe_get(raw, "home_team", "name", default=None) or raw.get("home_name") or "Local"
    away_name = safe_get(raw, "awayTeam", "name", default=None) or safe_get(raw, "away_team", "name", default=None) or raw.get("away_name") or "Visitante"

    home_logo = safe_get(raw, "homeTeam", "logo", default=None) or safe_get(raw, "home_team", "logo", default=None) or ""
    away_logo = safe_get(raw, "awayTeam", "logo", default=None) or safe_get(raw, "away_team", "logo", default=None) or ""

    league_name = safe_get(raw, "competition", "name", default=None) or safe_get(raw, "league", "name", default=None) or raw.get("competition_name") or ""
    country_name = safe_get(raw, "country", "name", default=None) or safe_get(raw, "area", "name", default=None) or raw.get("country_name") or ""

    utc_date = raw.get("date") or raw.get("utcDate") or raw.get("starting_at") or raw.get("kickoff") or ""
    match_date = utc_date[:10] if utc_date else ""

    home_score = safe_get(raw, "score", "home", default=None)
    away_score = safe_get(raw, "score", "away", default=None)

    if home_score is None:
        home_score = safe_get(raw, "scores", "home", default=None)
    if away_score is None:
        away_score = safe_get(raw, "scores", "away", default=None)

    return {
        "id": raw.get("id") or raw.get("fixture_id") or raw.get("match_id") or 0,
        "utcDate": utc_date,
        "matchDate": match_date,
        "status": raw.get("status") or "NS",
        "statusText": raw.get("status") or "SCHEDULED",
        "minute": raw.get("minute") or 0,
        "venue": raw.get("venue") or "",
        "matchday": raw.get("matchday") or 0,
        "homeTeam": {
            "id": safe_get(raw, "homeTeam", "id", default=None) or safe_get(raw, "home_team", "id", default=None),
            "name": home_name,
            "shortName": home_name[:15],
            "crest": home_logo
        },
        "awayTeam": {
            "id": safe_get(raw, "awayTeam", "id", default=None) or safe_get(raw, "away_team", "id", default=None),
            "name": away_name,
            "shortName": away_name[:15],
            "crest": away_logo
        },
        "competition": {
            "id": safe_get(raw, "competition", "id", default=None) or safe_get(raw, "league", "id", default=None),
            "name": league_name,
            "code": safe_get(raw, "competition", "code", default=None) or safe_get(raw, "league", "code", default=None) or ""
        },
        "league_name": league_name,
        "country": country_name,
        "homeScore": home_score,
        "awayScore": away_score,
        "halfTimeHome": None,
        "halfTimeAway": None
    }


def extract_list_payload(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["data", "fixtures", "matches", "response"]:
            if isinstance(data.get(key), list):
                return data.get(key)
    return []


def fetch_fdio_matches(date_str):
    data = fdio_request("fixtures/today", cache_key=f"fdio_today_{date_str}", ttl=180)
    items = extract_list_payload(data)
    matches = [normalize_match(x) for x in items]
    if date_str:
        matches = [m for m in matches if m["matchDate"] == date_str or not m["matchDate"]]
    return matches


def find_team_id(team_name):
    if not team_name:
        return None

    data = fdorg_request("teams", cache_key="fdorg_teams_all", ttl=86400)
    items = data.get("teams", []) if isinstance(data, dict) else []

    target = team_name.strip().lower()

    for team in items:
        names = [
            (team.get("name") or "").lower(),
            (team.get("shortName") or "").lower(),
            (team.get("tla") or "").lower()
        ]
        if target in names:
            return team.get("id")

    for team in items:
        names = [
            (team.get("name") or "").lower(),
            (team.get("shortName") or "").lower()
        ]
        if any(target in n or n in target for n in names if n):
            return team.get("id")

    return None


def get_team_recent_matches(team_id, limit=10):
    if not team_id:
        return []
    data = fdorg_request(
        f"teams/{team_id}/matches",
        params={"status": "FINISHED", "limit": limit},
        cache_key=f"fdorg_team_matches_{team_id}_{limit}",
        ttl=1800
    )
    if not data or not isinstance(data, dict):
        return []
    return data.get("matches", [])


def build_form_and_stats(team_id, matches):
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
        "clean_sheet_pct": round((clean_sheet / played) * 100, 1),
        "failed_to_score_pct": round((failed_to_score / played) * 100, 1)
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/matches")
def matches(date: str = Query(None)):
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    matches = fetch_fdio_matches(date)

    if matches:
        return {
            "matches": matches,
            "requested_date": date,
            "source_date": date,
            "is_exact": True,
            "source": "footballdata.io"
        }

    for delta in [-1, 1, -2, 2]:
        alt = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
        alt_matches = fetch_fdio_matches(alt)
        if alt_matches:
            return {
                "matches": alt_matches,
                "requested_date": date,
                "source_date": alt,
                "is_exact": False,
                "source": "footballdata.io"
            }

    return {
        "matches": [],
        "requested_date": date,
        "source_date": None,
        "is_exact": True,
        "source": "footballdata.io"
    }


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
    home_id = find_team_id(home_team)
    away_id = find_team_id(away_team)

    home_recent = get_team_recent_matches(home_id, 10)
    away_recent = get_team_recent_matches(away_id, 10)

    home_form, home_stats = build_form_and_stats(home_id, home_recent)
    away_form, away_stats = build_form_and_stats(away_id, away_recent)

    probabilities = {
        "over_1_5": round((home_stats["over_1_5_pct"] + away_stats["over_1_5_pct"]) / 2, 1),
        "over_2_5": round((home_stats["over_2_5_pct"] + away_stats["over_2_5_pct"]) / 2, 1),
        "over_3_5": round((home_stats["over_3_5_pct"] + away_stats["over_3_5_pct"]) / 2, 1),
        "btts": round((home_stats["btts_pct"] + away_stats["btts_pct"]) / 2, 1),
        "total_expected_goals": round(home_stats["avg_team_goals"] + away_stats["avg_team_goals"], 2),
        "expected_corners": None,
        "expected_cards": None
    }

    return JSONResponse({
        "match_info": {
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
        },
        "home_form": home_form,
        "away_form": away_form,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "h2h": {"matches": [], "stats": {}},
        "probabilities": probabilities,
        "odds": {"home": 0, "draw": 0, "away": 0},
        "stats_available": bool(home_stats["played"] or away_stats["played"]),
        "debug": {
            "match_id": match_id,
            "home_id": home_id,
            "away_id": away_id,
            "home_recent_count": len(home_recent),
            "away_recent_count": len(away_recent)
        }
    })


@app.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "cache_size": len(CACHE),
        "footballdata_io": "configured" if FOOTBALLDATA_IO_KEY else "missing",
        "football_data_org": "configured" if FOOTBALL_DATA_ORG_KEY else "missing",
        "version": "5.0.0"
    }
