import os
import logging
from datetime import datetime

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
        logger.error("FOOTBALLDATA_IO_KEY missing")
        return None
    return api_get(FDIO_BASE, endpoint, FDIO_HEADERS, params, cache_key, ttl)


def fdorg_request(endpoint, params=None, cache_key=None, ttl=300):
    if not FOOTBALL_DATA_ORG_KEY:
        logger.error("API_FOOTBALL_KEY missing")
        return None
    return api_get(FDORG_BASE, endpoint, FDORG_HEADERS, params, cache_key, ttl)


def safe_get(d, *keys, default=None):
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def extract_list_payload(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["data", "fixtures", "matches", "response"]:
            value = data.get(key)
            if isinstance(value, list):
                return value

        if isinstance(data.get("data"), dict):
            for key in ["fixtures", "matches", "response"]:
                value = data["data"].get(key)
                if isinstance(value, list):
                    return value

    return []


def normalize_match(raw):
    league = raw.get("league", {}) or {}
    home = raw.get("home_team", {}) or {}
    away = raw.get("away_team", {}) or {}
    venue = raw.get("venue", {}) or {}
    score = raw.get("score", {}) or {}
    xg = raw.get("xg", {}) or {}
    odds = raw.get("odds", {}) or {}
    probabilities = raw.get("probabilities", {}) or {}

    utc_date = raw.get("match_date", "") or ""

    return {
        "id": raw.get("match_id") or raw.get("id") or 0,
        "utcDate": utc_date,
        "matchDate": utc_date[:10] if utc_date else "",
        "status": raw.get("status", "NS"),
        "statusText": raw.get("status", "NS"),
        "minute": 0,
        "venue": venue.get("stadium_name", "") or "",
        "matchday": raw.get("game_week", 0) or 0,
        "homeTeam": {
            "id": home.get("team_id"),
            "name": home.get("team_name", "Local"),
            "shortName": home.get("team_name", "Local")[:15],
            "crest": home.get("team_logo", "") or ""
        },
        "awayTeam": {
            "id": away.get("team_id"),
            "name": away.get("team_name", "Visitante"),
            "shortName": away.get("team_name", "Visitante")[:15],
            "crest": away.get("team_logo", "") or ""
        },
        "competition": {
            "id": league.get("league_id"),
            "name": league.get("competition_name", "") or league.get("name", ""),
            "code": ""
        },
        "league_name": league.get("competition_name", "") or league.get("name", ""),
        "country": league.get("country", ""),
        "homeScore": score.get("home"),
        "awayScore": score.get("away"),
        "halfTimeHome": None,
        "halfTimeAway": None,
        "xg_home": xg.get("home"),
        "xg_away": xg.get("away"),
        "xg_total": xg.get("total"),
        "odds_home": odds.get("home_win"),
        "odds_draw": odds.get("draw"),
        "odds_away": odds.get("away_win"),
        "prob_home": probabilities.get("home_win"),
        "prob_draw": probabilities.get("draw"),
        "prob_away": probabilities.get("away_win")
    }


def fetch_fdio_matches(date_str):
    raw = fdio_request("fixtures/today", cache_key=f"fdio_today_{date_str}", ttl=180)
    items = extract_list_payload(raw)
    matches = [normalize_match(x) for x in items]

    if date_str:
        matches = [m for m in matches if m["matchDate"] == date_str]

    return matches


def normalize_name(name):
    if not name:
        return ""
    text = name.strip().lower()
    replacements = {
        " cf": "",
        " fc": "",
        " sad": "",
        " de futbol": "",
        " fútbol": "",
        " balompié": " balompie",
        ".": "",
        ",": "",
        "-": " ",
        "  ": " "
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def get_fdorg_competitions():
    data = fdorg_request("competitions", cache_key="fdorg_competitions", ttl=86400)
    if not data or not isinstance(data, dict):
        return []
    return data.get("competitions", [])


def resolve_competition(league_name, country_name=""):
    comps = get_fdorg_competitions()
    target_league = normalize_name(league_name)
    target_country = normalize_name(country_name)

    for comp in comps:
        comp_name = normalize_name(comp.get("name", ""))
        area_name = normalize_name(safe_get(comp, "area", "name", default=""))
        code = comp.get("code", "")
        if comp_name == target_league and (not target_country or area_name == target_country):
            return {"id": comp.get("id"), "code": code, "name": comp.get("name")}
    for comp in comps:
        comp_name = normalize_name(comp.get("name", ""))
        area_name = normalize_name(safe_get(comp, "area", "name", default=""))
        code = comp.get("code", "")
        if target_league in comp_name or comp_name in target_league:
            if not target_country or area_name == target_country:
                return {"id": comp.get("id"), "code": code, "name": comp.get("name")}
    return None


def find_team_id(team_name, competition_id=None):
    if not team_name:
        return None

    target = normalize_name(team_name)

    if competition_id:
        comp_data = fdorg_request(
            f"competitions/{competition_id}/teams",
            cache_key=f"comp_teams_{competition_id}",
            ttl=86400
        )
        if comp_data and isinstance(comp_data, dict):
            teams = comp_data.get("teams", [])

            for team in teams:
                options = [
                    normalize_name(team.get("name", "")),
                    normalize_name(team.get("shortName", "")),
                    normalize_name(team.get("tla", ""))
                ]
                if target in options:
                    return team.get("id")

            for team in teams:
                options = [
                    normalize_name(team.get("name", "")),
                    normalize_name(team.get("shortName", ""))
                ]
                if any(target == opt or target in opt or opt in target for opt in options if opt):
                    return team.get("id")

    data = fdorg_request("teams", params={"limit": 500}, cache_key="fdorg_all_teams_500", ttl=86400)
    if not data or not isinstance(data, dict):
        return None

    teams = data.get("teams", [])

    for team in teams:
        options = [
            normalize_name(team.get("name", "")),
            normalize_name(team.get("shortName", "")),
            normalize_name(team.get("tla", ""))
        ]
        if target in options:
            return team.get("id")

    for team in teams:
        options = [
            normalize_name(team.get("name", "")),
            normalize_name(team.get("shortName", ""))
        ]
        if any(target == opt or target in opt or opt in target for opt in options if opt):
            return team.get("id")

    return None


def get_team_recent_matches(team_id, competition_id=None, limit=10):
    if not team_id:
        return []

    params = {
        "status": "FINISHED",
        "limit": limit
    }

    if competition_id:
        params["competitions"] = str(competition_id)

    data = fdorg_request(
        f"teams/{team_id}/matches",
        params=params,
        cache_key=f"fdorg_recent_{team_id}_{competition_id}_{limit}",
        ttl=1800
    )

    matches = data.get("matches", []) if isinstance(data, dict) else []

    if not matches:
        data = fdorg_request(
            f"teams/{team_id}/matches",
            params={"status": "FINISHED", "limit": limit},
            cache_key=f"fdorg_recent_fallback_{team_id}_{limit}",
            ttl=1800
        )
        matches = data.get("matches", []) if isinstance(data, dict) else []

    return matches


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
        "form_string": "".join([f["result"] for f in form]),
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

    return {
        "matches": matches,
        "requested_date": date,
        "source_date": date if matches else None,
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
    country: str = Query(""),
    venue: str = Query(""),
    home_score: float = Query(None),
    away_score: float = Query(None),
    xg_home: float = Query(None),
    xg_away: float = Query(None),
    xg_total: float = Query(None),
    odds_home: float = Query(None),
    odds_draw: float = Query(None),
    odds_away: float = Query(None),
    prob_home: float = Query(None),
    prob_draw: float = Query(None),
    prob_away: float = Query(None)
):
    competition = resolve_competition(league, country)
    competition_id = competition["id"] if competition else None

    home_id = find_team_id(home_team, competition_id)
    away_id = find_team_id(away_team, competition_id)

    home_recent = get_team_recent_matches(home_id, competition_id, 10)
    away_recent = get_team_recent_matches(away_id, competition_id, 10)

    home_form, home_stats = build_form_and_stats(home_id, home_recent)
    away_form, away_stats = build_form_and_stats(away_id, away_recent)

    probabilities = {
        "home_win": prob_home if prob_home is not None else 0,
        "draw": prob_draw if prob_draw is not None else 0,
        "away_win": prob_away if prob_away is not None else 0,
        "over_1_5": round((home_stats["over_1_5_pct"] + away_stats["over_1_5_pct"]) / 2, 1),
        "over_2_5": round((home_stats["over_2_5_pct"] + away_stats["over_2_5_pct"]) / 2, 1),
        "over_3_5": round((home_stats["over_3_5_pct"] + away_stats["over_3_5_pct"]) / 2, 1),
        "btts": round((home_stats["btts_pct"] + away_stats["btts_pct"]) / 2, 1),
        "total_expected_goals": xg_total if xg_total is not None else round(home_stats["avg_team_goals"] + away_stats["avg_team_goals"], 2),
        "home_xg": xg_home if xg_home is not None else 0,
        "away_xg": xg_away if xg_away is not None else 0
    }

    odds = {
        "home": odds_home if odds_home is not None else 0,
        "draw": odds_draw if odds_draw is not None else 0,
        "away": odds_away if odds_away is not None else 0
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
            "venue": venue,
            "status": "SCHEDULED",
            "minute": 0,
            "matchday": 0,
            "home_score": home_score,
            "away_score": away_score,
            "halfTimeHome": None,
            "halfTimeAway": None
        },
        "home_form": home_form,
        "away_form": away_form,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "h2h": {"matches": [], "stats": {}},
        "probabilities": probabilities,
        "odds": odds,
        "stats_available": bool(home_stats["played"] or away_stats["played"]),
        "debug": {
            "match_id": match_id,
            "competition": competition,
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
        "version": "8.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
