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

app = FastAPI(title="TipFactory", version="5.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

FOOTBALL_DATA_ORG_KEY = os.environ.get("API_FOOTBALL_KEY", "").strip()
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": FOOTBALL_DATA_ORG_KEY} if FOOTBALL_DATA_ORG_KEY else {}

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

    if not FOOTBALL_DATA_ORG_KEY:
        logger.error("API_FOOTBALL_KEY missing")
        return None

    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)

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
        logger.error(f"API error {endpoint}: {e}")
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
    comp = m.get("competition", {}) or {}
    area = m.get("area", {}) or comp.get("area", {}) or {}
    score = m.get("score", {}) or {}
    ft = score.get("fullTime", {}) or {}
    ht = score.get("halfTime", {}) or {}

    utc = m.get("utcDate", "")
    return {
        "id": m.get("id"),
        "utcDate": utc,
        "matchDate": utc[:10] if utc else "",
        "status": m.get("status", "SCHEDULED"),
        "statusText": m.get("status", "SCHEDULED"),
        "minute": 0,
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


def dedupe_matches(matches):
    seen = set()
    out = []
    for m in matches:
        mid = m.get("id")
        if mid and mid not in seen:
            seen.add(mid)
            out.append(m)
    return out


def fetch_matches_for_date(date_str):
    matches = []

    general = api_request(
        "matches",
        params={"dateFrom": date_str, "dateTo": date_str},
        cache_key=f"matches_{date_str}",
        ttl=300
    )

    if general and general.get("matches"):
        matches.extend([format_match(m) for m in general["matches"]])

    if not matches:
        for code in TOP_COMPETITIONS:
            data = api_request(
                f"competitions/{code}/matches",
                params={"dateFrom": date_str, "dateTo": date_str},
                cache_key=f"comp_{code}_{date_str}",
                ttl=600
            )
            if data and data.get("matches"):
                matches.extend([format_match(m) for m in data["matches"]])

    matches = [m for m in dedupe_matches(matches) if m["matchDate"] == date_str]
    logger.info(f"MATCHES {date_str}: {len(matches)}")
    return matches


def find_team_id(team_name):
    if not team_name:
        return None

    data = api_request("teams", cache_key="all_teams", ttl=86400)
    if not data or not data.get("teams"):
        return None

    target = team_name.strip().lower()

    for team in data["teams"]:
        names = [
            (team.get("name") or "").lower(),
            (team.get("shortName") or "").lower(),
            (team.get("tla") or "").lower()
        ]
        if target in names:
            return team.get("id")

    for team in data["teams"]:
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
    data = api_request(
        f"teams/{team_id}/matches",
        params={"status": "FINISHED", "limit": limit},
        cache_key=f"team_recent_{team_id}_{limit}",
        ttl=1800
    )
    if not data or not data.get("matches"):
        return []
    return data["matches"]


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

    exact = fetch_matches_for_date(date)
    if exact:
        return {
            "matches": exact,
            "requested_date": date,
            "source_date": date,
            "is_exact": True,
            "source": "football-data.org"
        }

    for delta in [-1, 1, -2, 2, -3, 3]:
        alt_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
        alt = fetch_matches_for_date(alt_date)
        if alt:
            return {
                "matches": alt,
                "requested_date": date,
                "source_date": alt_date,
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


@app.get("/api/test-matches")
def test_matches(date: str = Query(None)):
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    raw = api_request(
        "matches",
        params={"dateFrom": date, "dateTo": date},
        cache_key=None,
        ttl=0
    )

    return {
        "date": date,
        "has_data": bool(raw),
        "match_count": len(raw.get("matches", [])) if isinstance(raw, dict) else 0,
        "sample": raw.get("matches", [])[:2] if isinstance(raw, dict) else []
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
        "football_data_org": "configured" if FOOTBALL_DATA_ORG_KEY else "missing",
        "version": "5.1.0"
    }
