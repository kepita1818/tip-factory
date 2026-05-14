import os
import logging
from datetime import datetime, timedelta

import requests
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TipFactory", version="2.1.0")

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

_cache = {}

TOP_COMPETITIONS = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "PPL": "Primeira Liga",
    "DED": "Eredivisie",
    "ELC": "Championship",
    "BSA": "Brazil Serie A",
    "CL": "Champions League",
    "EL": "Europa League"
}


def get_cache(key, ttl=300):
    if key in _cache:
        data, ts = _cache[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None


def set_cache(key, data):
    _cache[key] = (data, datetime.now())


def api_request(endpoint, params=None, cache_key=None, ttl=300):
    if cache_key:
        cached = get_cache(cache_key, ttl)
        if cached is not None:
            return cached

    if not API_KEY:
        logger.error("API_FOOTBALL_KEY no configurada")
        return None

    try:
        url = f"{BASE_URL}/{endpoint}"
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)

        if resp.status_code == 429:
            logger.error(f"RATE LIMIT en {endpoint}")
            return None
        if resp.status_code in (401, 403):
            logger.error(f"AUTH ERROR {resp.status_code} en {endpoint}")
            return None
        if resp.status_code == 404:
            logger.warning(f"NOT FOUND {endpoint}")
            return None

        resp.raise_for_status()
        data = resp.json()

        if cache_key:
            set_cache(cache_key, data)

        return data
    except Exception as e:
        logger.error(f"API error en {endpoint}: {e}")
        return None


def dedupe_matches(matches):
    seen = set()
    unique = []
    for m in matches:
        match_id = m.get("id")
        if match_id and match_id not in seen:
            seen.add(match_id)
            unique.append(m)
    return unique


def format_match(m):
    home = m.get("homeTeam", {}) or {}
    away = m.get("awayTeam", {}) or {}
    competition = m.get("competition", {}) or {}
    area = m.get("area", {}) or competition.get("area", {}) or {}
    score = m.get("score", {}) if isinstance(m.get("score", {}), dict) else {}
    ft = score.get("fullTime", {}) if isinstance(score.get("fullTime", {}), dict) else {}
    ht = score.get("halfTime", {}) if isinstance(score.get("halfTime", {}), dict) else {}

    utc_date = m.get("utcDate", "")
    match_date = utc_date[:10] if utc_date else ""

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
        "utcDate": utc_date,
        "matchDate": match_date,
        "status": status_map.get(status, status),
        "statusText": status,
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
            "id": competition.get("id"),
            "name": competition.get("name", ""),
            "code": competition.get("code", "")
        },
        "league_name": competition.get("name", ""),
        "country": area.get("name", ""),
        "homeScore": ft.get("home"),
        "awayScore": ft.get("away"),
        "halfTimeHome": ht.get("home"),
        "halfTimeAway": ht.get("away")
    }


def fetch_matches_for_date(date_str):
    all_matches = []
    found_competitions = set()

    general = api_request(
        "matches",
        params={"dateFrom": date_str, "dateTo": date_str},
        cache_key=f"matches_{date_str}",
        ttl=300
    )

    if general and general.get("matches"):
        all_matches.extend([format_match(m) for m in general["matches"]])

    for comp_code, comp_name in TOP_COMPETITIONS.items():
        data = api_request(
            f"competitions/{comp_code}/matches",
            params={"dateFrom": date_str, "dateTo": date_str},
            cache_key=f"comp_{comp_code}_{date_str}",
            ttl=600
        )
        if data and data.get("matches"):
            comp_matches = [format_match(m) for m in data["matches"]]
            if comp_matches:
                all_matches.extend(comp_matches)
                found_competitions.add(comp_name)

    all_matches = [m for m in dedupe_matches(all_matches) if m["matchDate"] == date_str]
    return all_matches, list(found_competitions)


def classify_result(tg, og):
    if tg > og:
        return "W"
    if tg < og:
        return "L"
    return "D"


def build_recent_form(team_id, matches, limit=5):
    form = []

    for m in matches:
        if m.get("status") != "FINISHED":
            continue

        home = m.get("homeTeam", {}) or {}
        away = m.get("awayTeam", {}) or {}
        score = m.get("score", {}).get("fullTime", {})
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
        opponent = away.get("name", "Rival") if is_home else home.get("name", "Rival")

        form.append({
            "result": classify_result(tg, og),
            "result_text": "Victoria" if tg > og else "Empate" if tg == og else "Derrota",
            "team_goals": tg,
            "opp_goals": og,
            "opponent": opponent,
            "venue": "home" if is_home else "away",
            "date": (m.get("utcDate") or "")[:10],
            "competition": m.get("competition", {}).get("name", "")
        })

        if len(form) >= limit:
            break

    return form


def filter_by_comp(matches, comp_code):
    if not comp_code:
        return matches
    filtered = []
    for m in matches:
        code = (m.get("competition", {}) or {}).get("code")
        if code == comp_code:
            filtered.append(m)
    return filtered


def season_stats_for_team(team_id, matches):
    played = won = draw = lost = 0
    goals_for = goals_against = 0
    btts = over15 = over25 = over35 = 0
    clean_sheet = failed_to_score = 0
    home_played = away_played = 0
    home_goals_for = away_goals_for = 0

    for m in matches:
        if m.get("status") != "FINISHED":
            continue

        home = m.get("homeTeam", {}) or {}
        away = m.get("awayTeam", {}) or {}
        score = m.get("score", {}).get("fullTime", {})
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
        goals_for += tg
        goals_against += og

        if is_home:
            home_played += 1
            home_goals_for += tg
        else:
            away_played += 1
            away_goals_for += tg

        if tg > og:
            won += 1
        elif tg == og:
            draw += 1
        else:
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

    if played == 0:
        return {
            "played": 0, "won": 0, "draw": 0, "lost": 0,
            "goals_for": 0, "goals_against": 0, "points": 0,
            "avg_total_goals": 0, "avg_team_goals": 0, "avg_conceded": 0,
            "btts_pct": 0, "over_1_5_pct": 0, "over_2_5_pct": 0, "over_3_5_pct": 0,
            "clean_sheet_pct": 0, "failed_to_score_pct": 0,
            "home_avg_goals_for": 0, "away_avg_goals_for": 0
        }

    return {
        "played": played,
        "won": won,
        "draw": draw,
        "lost": lost,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "points": won * 3 + draw,
        "avg_total_goals": round((goals_for + goals_against) / played, 2),
        "avg_team_goals": round(goals_for / played, 2),
        "avg_conceded": round(goals_against / played, 2),
        "btts_pct": round((btts / played) * 100, 1),
        "over_1_5_pct": round((over15 / played) * 100, 1),
        "over_2_5_pct": round((over25 / played) * 100, 1),
        "over_3_5_pct": round((over35 / played) * 100, 1),
        "clean_sheet_pct": round((clean_sheet / played) * 100, 1),
        "failed_to_score_pct": round((failed_to_score / played) * 100, 1),
        "home_avg_goals_for": round(home_goals_for / home_played, 2) if home_played else 0,
        "away_avg_goals_for": round(away_goals_for / away_played, 2) if away_played else 0
    }


def get_team_matches(team_id, season_year):
    data = api_request(
        f"teams/{team_id}/matches",
        params={"status": "FINISHED", "season": season_year, "limit": 100},
        cache_key=f"team_matches_{team_id}_{season_year}",
        ttl=1800
    )
    if not data or not data.get("matches"):
        return []
    return data["matches"]


def get_standings(team_id, comp_code, season_year):
    if not comp_code:
        return None

    data = api_request(
        f"competitions/{comp_code}/standings",
        params={"season": season_year},
        cache_key=f"standings_{comp_code}_{season_year}",
        ttl=3600
    )

    if not data or not data.get("standings"):
        logger.warning(f"Sin standings para {comp_code} {season_year}")
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

    logger.info(f"BUSCANDO PARTIDOS PARA: {date}")

    exact_matches, competitions_found = fetch_matches_for_date(date)
    if exact_matches:
        return {
            "matches": exact_matches,
            "requested_date": date,
            "source_date": date,
            "is_exact": True,
            "competitions_found": competitions_found
        }

    for delta in [-1, 1, -2, 2, -3, 3]:
        check_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
        alt_matches, alt_comps = fetch_matches_for_date(check_date)
        if alt_matches:
            return {
                "matches": alt_matches,
                "requested_date": date,
                "source_date": check_date,
                "is_exact": False,
                "competitions_found": alt_comps
            }

    return {
        "matches": [],
        "requested_date": date,
        "source_date": None,
        "is_exact": True,
        "competitions_found": []
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
    logger.info(f"ANALIZANDO PARTIDO {match_id}")

    match = api_request(f"matches/{match_id}", cache_key=f"match_{match_id}", ttl=300)
    if not match:
        logger.warning(f"No se pudo cargar matches/{match_id}")
        return {
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
                "time": time
            },
            "home_form": [],
            "away_form": [],
            "home_stats": {},
            "away_stats": {},
            "h2h": {"matches": [], "stats": {}},
            "probabilities": {
                "over_1_5": None,
                "over_2_5": None,
                "over_3_5": None,
                "btts": None,
                "total_expected_goals": None,
                "expected_corners": None,
                "expected_cards": None
            },
            "odds": {"home": 0, "draw": 0, "away": 0},
            "stats_available": False
        }

    home_data = match.get("homeTeam", {}) or {}
    away_data = match.get("awayTeam", {}) or {}
    competition = match.get("competition", {}) or {}
    area = match.get("area", {}) or competition.get("area", {}) or {}
    season = match.get("season", {}) or {}

    home_id = home_data.get("id")
    away_id = away_data.get("id")
    comp_code = competition.get("code")
    season_year = int((season.get("startDate") or "2025-08-01")[:4])

    logger.info(f"Partido {match_id}: comp_code={comp_code}, season_year={season_year}, home_id={home_id}, away_id={away_id}")

    home_matches = get_team_matches(home_id, season_year)
    away_matches = get_team_matches(away_id, season_year)

    logger.info(f"Home matches raw: {len(home_matches)} | Away matches raw: {len(away_matches)}")

    home_comp_matches = filter_by_comp(home_matches, comp_code)
    away_comp_matches = filter_by_comp(away_matches, comp_code)

    logger.info(f"Home comp matches: {len(home_comp_matches)} | Away comp matches: {len(away_comp_matches)}")

    if not home_comp_matches:
      home_comp_matches = home_matches
    if not away_comp_matches:
      away_comp_matches = away_matches

    home_stats = season_stats_for_team(home_id, home_comp_matches)
    away_stats = season_stats_for_team(away_id, away_comp_matches)

    home_form = build_recent_form(home_id, home_comp_matches, 5)
    away_form = build_recent_form(away_id, away_comp_matches, 5)

    home_standings = get_standings(home_id, comp_code, season_year)
    away_standings = get_standings(away_id, comp_code, season_year)

    if home_standings:
        home_stats["position"] = home_standings.get("position", 0)
        home_stats["form_string"] = home_standings.get("form", "")
    else:
        home_stats["position"] = 0
        home_stats["form_string"] = ""

    if away_standings:
        away_stats["position"] = away_standings.get("position", 0)
        away_stats["form_string"] = away_standings.get("form", "")
    else:
        away_stats["position"] = 0
        away_stats["form_string"] = ""

    stats_available = bool(home_stats.get("played") or away_stats.get("played"))

    probabilities = {
        "over_1_5": round((home_stats.get("over_1_5_pct", 0) + away_stats.get("over_1_5_pct", 0)) / 2, 1) if stats_available else None,
        "over_2_5": round((home_stats.get("over_2_5_pct", 0) + away_stats.get("over_2_5_pct", 0)) / 2, 1) if stats_available else None,
        "over_3_5": round((home_stats.get("over_3_5_pct", 0) + away_stats.get("over_3_5_pct", 0)) / 2, 1) if stats_available else None,
        "btts": round((home_stats.get("btts_pct", 0) + away_stats.get("btts_pct", 0)) / 2, 1) if stats_available else None,
        "total_expected_goals": round(home_stats.get("home_avg_goals_for", 0) + away_stats.get("away_avg_goals_for", 0), 2) if stats_available else None,
        "expected_corners": None,
        "expected_cards": None
    }

    logger.info(f"stats_available={stats_available} | home_played={home_stats.get('played')} | away_played={away_stats.get('played')}")

    return {
        "match_info": {
            "home_team": home_data.get("name", home_team),
            "away_team": away_data.get("name", away_team),
            "home_short": home_data.get("shortName") or home_data.get("tla") or home_data.get("name", home_team)[:12],
            "away_short": away_data.get("shortName") or away_data.get("tla") or away_data.get("name", away_team)[:12],
            "home_logo": home_data.get("crest", "") or home_logo,
            "away_logo": away_data.get("crest", "") or away_logo,
            "league": competition.get("name", league),
            "country": area.get("name", country),
            "date": (match.get("utcDate") or "")[:10] if match.get("utcDate") else date,
            "time": (match.get("utcDate") or "")[11:16] if match.get("utcDate") else time,
            "venue": match.get("venue", "") or "",
            "status": match.get("status", "SCHEDULED"),
            "minute": 0,
            "matchday": match.get("matchday", 0) or 0,
            "home_score": match.get("score", {}).get("fullTime", {}).get("home"),
            "away_score": match.get("score", {}).get("fullTime", {}).get("away"),
            "halfTimeHome": match.get("score", {}).get("halfTime", {}).get("home"),
            "halfTimeAway": match.get("score", {}).get("halfTime", {}).get("away")
        },
        "home_form": home_form,
        "away_form": away_form,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "h2h": {"matches": [], "stats": {}},
        "probabilities": probabilities,
        "odds": {"home": 0, "draw": 0, "away": 0},
        "stats_available": stats_available
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "cache_size": len(_cache),
        "time": datetime.now().isoformat(),
        "api_key": "configured" if API_KEY else "missing"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
