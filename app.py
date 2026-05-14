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

app = FastAPI(title="TipFactory", version="2.0.0")

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
    "EL": "Europa League",
    "EC": "Euro Cup"
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
        if not match_id:
            continue
        if match_id not in seen:
            seen.add(match_id)
            unique.append(m)
    return unique


def safe_score(score_obj, side):
    if not isinstance(score_obj, dict):
        return None
    return score_obj.get(side)


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

    minute = m.get("minute", 0)
    if isinstance(minute, dict):
        minute = minute.get("regular", 0)

    return {
        "id": m.get("id"),
        "utcDate": utc_date,
        "matchDate": match_date,
        "status": status_map.get(status, status),
        "statusText": status,
        "minute": minute or 0,
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
        "homeScore": safe_score(ft, "home"),
        "awayScore": safe_score(ft, "away"),
        "halfTimeHome": safe_score(ht, "home"),
        "halfTimeAway": safe_score(ht, "away")
    }


def fetch_matches_for_date(date_str):
    all_matches = []
    found_competitions = set()

    general_data = api_request(
        "matches",
        params={"dateFrom": date_str, "dateTo": date_str},
        cache_key=f"matches_{date_str}",
        ttl=300
    )

    if general_data and general_data.get("matches"):
        general_matches = [format_match(m) for m in general_data["matches"]]
        general_matches = [m for m in general_matches if m["matchDate"] == date_str]
        all_matches.extend(general_matches)

    for comp_code, comp_name in TOP_COMPETITIONS.items():
        data = api_request(
            f"competitions/{comp_code}/matches",
            params={"dateFrom": date_str, "dateTo": date_str},
            cache_key=f"comp_{comp_code}_{date_str}",
            ttl=600
        )

        if data and data.get("matches"):
            comp_matches = [format_match(m) for m in data["matches"]]
            comp_matches = [m for m in comp_matches if m["matchDate"] == date_str]
            if comp_matches:
                all_matches.extend(comp_matches)
                found_competitions.add(comp_name)

    return dedupe_matches(all_matches), list(found_competitions)


def classify_result(team_goals, opp_goals):
    if team_goals > opp_goals:
        return "W"
    if team_goals < opp_goals:
        return "L"
    return "D"


def build_recent_form(team_id, matches, limit=5):
    form = []

    for m in matches:
        home = m.get("homeTeam", {}) or {}
        away = m.get("awayTeam", {}) or {}
        score = m.get("score", {}).get("fullTime", {})
        hg = score.get("home")
        ag = score.get("away")

        if hg is None or ag is None:
            continue

        is_home = home.get("id") == team_id
        if not is_home and away.get("id") != team_id:
            continue

        if is_home:
            tg = hg
            og = ag
            opponent = away.get("name", "Rival")
        else:
            tg = ag
            og = hg
            opponent = home.get("name", "Rival")

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


def season_stats_for_team(team_id, matches):
    played = 0
    won = 0
    draw = 0
    lost = 0
    goals_for = 0
    goals_against = 0
    btts = 0
    over_15 = 0
    over_25 = 0
    over_35 = 0
    clean_sheets = 0
    failed_to_score = 0

    home_played = 0
    away_played = 0
    home_goals_for = 0
    away_goals_for = 0
    home_goals_against = 0
    away_goals_against = 0

    valid_matches = []

    for m in matches:
        status = m.get("status")
        if status != "FINISHED":
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

        played += 1
        valid_matches.append(m)

        if is_home:
            tg = hg
            og = ag
            home_played += 1
            home_goals_for += tg
            home_goals_against += og
        else:
            tg = ag
            og = hg
            away_played += 1
            away_goals_for += tg
            away_goals_against += og

        goals_for += tg
        goals_against += og

        if tg > og:
            won += 1
        elif tg == og:
            draw += 1
        else:
            lost += 1

        total_goals = tg + og
        if total_goals > 1:
            over_15 += 1
        if total_goals > 2:
            over_25 += 1
        if total_goals > 3:
            over_35 += 1
        if tg > 0 and og > 0:
            btts += 1
        if og == 0:
            clean_sheets += 1
        if tg == 0:
            failed_to_score += 1

    if played == 0:
        return {
            "played": 0,
            "won": 0,
            "draw": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
            "avg_total_goals": 0,
            "avg_team_goals": 0,
            "avg_conceded": 0,
            "btts_pct": 0,
            "over_1_5_pct": 0,
            "over_2_5_pct": 0,
            "over_3_5_pct": 0,
            "clean_sheet_pct": 0,
            "failed_to_score_pct": 0,
            "home_avg_goals_for": 0,
            "away_avg_goals_for": 0,
            "home_avg_goals_against": 0,
            "away_avg_goals_against": 0,
            "recent_matches": []
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
        "over_1_5_pct": round((over_15 / played) * 100, 1),
        "over_2_5_pct": round((over_25 / played) * 100, 1),
        "over_3_5_pct": round((over_35 / played) * 100, 1),
        "clean_sheet_pct": round((clean_sheets / played) * 100, 1),
        "failed_to_score_pct": round((failed_to_score / played) * 100, 1),
        "home_avg_goals_for": round(home_goals_for / home_played, 2) if home_played else 0,
        "away_avg_goals_for": round(away_goals_for / away_played, 2) if away_played else 0,
        "home_avg_goals_against": round(home_goals_against / home_played, 2) if home_played else 0,
        "away_avg_goals_against": round(away_goals_against / away_played, 2) if away_played else 0,
        "recent_matches": valid_matches[:5]
    }


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


def get_team_season_matches(team_id, season_year):
    data = api_request(
        f"teams/{team_id}/matches",
        params={"status": "FINISHED", "season": season_year, "limit": 100},
        cache_key=f"team_matches_{team_id}_{season_year}",
        ttl=1800
    )

    if not data or not data.get("matches"):
        return []

    return data["matches"]


def filter_matches_by_competition(matches, comp_code):
    if not comp_code:
        return matches
    return [m for m in matches if (m.get("competition", {}) or {}).get("code") == comp_code]


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
        alt_matches, alt_competitions = fetch_matches_for_date(check_date)

        if alt_matches:
            return {
                "matches": alt_matches,
                "requested_date": date,
                "source_date": check_date,
                "is_exact": False,
                "competitions_found": alt_competitions
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

    match = api_request(
        f"matches/{match_id}",
        cache_key=f"match_{match_id}",
        ttl=300
    )

    if not match:
        return {
            "match_info": {
                "home_team": home_team,
                "away_team": away_team,
                "home_short": home_team[:12],
                "away_short": away_team[:12],
                "home_logo": home_logo,
                "away_logo": away_logo,
                "home_formation": "",
                "away_formation": "",
                "home_coach": "",
                "away_coach": "",
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
            "home_form": [],
            "away_form": [],
            "home_stats": {
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
                "failed_to_score_pct": 0,
                "avg_corners": None,
                "avg_cards": None
            },
            "away_stats": {
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
                "failed_to_score_pct": 0,
                "avg_corners": None,
                "avg_cards": None
            },
            "h2h": {"matches": [], "stats": {"home_wins": 0, "away_wins": 0, "draws": 0, "home_goals": 0, "away_goals": 0, "total_matches": 0}},
            "probabilities": {
                "over_1_5": 0,
                "over_2_5": 0,
                "over_3_5": 0,
                "btts": 0,
                "total_expected_goals": 0,
                "expected_corners": None,
                "expected_cards": None
            },
            "odds": {"home": 0, "draw": 0, "away": 0}
        }

    home_team_data = match.get("homeTeam", {}) or {}
    away_team_data = match.get("awayTeam", {}) or {}
    competition = match.get("competition", {}) or {}
    area = match.get("area", {}) or competition.get("area", {}) or {}
    season = match.get("season", {}) or {}
    season_year = int((season.get("startDate") or "2025")[:4])
    comp_code = competition.get("code")

    home_id = home_team_data.get("id")
    away_id = away_team_data.get("id")

    home_all_matches = get_team_season_matches(home_id, season_year)
    away_all_matches = get_team_season_matches(away_id, season_year)

    home_comp_matches = filter_matches_by_competition(home_all_matches, comp_code)
    away_comp_matches = filter_matches_by_competition(away_all_matches, comp_code)

    home_season = season_stats_for_team(home_id, home_comp_matches)
    away_season = season_stats_for_team(away_id, away_comp_matches)

    home_form = build_recent_form(home_id, home_comp_matches, 5)
    away_form = build_recent_form(away_id, away_comp_matches, 5)

    home_standings = get_standings(home_id, comp_code, season_year)
    away_standings = get_standings(away_id, comp_code, season_year)

    home_stats = {
        "position": home_standings["position"] if home_standings else 0,
        "played": home_season["played"],
        "won": home_season["won"],
        "draw": home_season["draw"],
        "lost": home_season["lost"],
        "goals_for": home_season["goals_for"],
        "goals_against": home_season["goals_against"],
        "points": home_season["points"],
        "form_string": home_standings["form"] if home_standings else "",
        "avg_total_goals": home_season["avg_total_goals"],
        "avg_team_goals": home_season["avg_team_goals"],
        "avg_conceded": home_season["avg_conceded"],
        "btts_pct": home_season["btts_pct"],
        "over_1_5_pct": home_season["over_1_5_pct"],
        "over_2_5_pct": home_season["over_2_5_pct"],
        "over_3_5_pct": home_season["over_3_5_pct"],
        "clean_sheet_pct": home_season["clean_sheet_pct"],
        "failed_to_score_pct": home_season["failed_to_score_pct"],
        "avg_corners": None,
        "avg_cards": None
    }

    away_stats = {
        "position": away_standings["position"] if away_standings else 0,
        "played": away_season["played"],
        "won": away_season["won"],
        "draw": away_season["draw"],
        "lost": away_season["lost"],
        "goals_for": away_season["goals_for"],
        "goals_against": away_season["goals_against"],
        "points": away_season["points"],
        "form_string": away_standings["form"] if away_standings else "",
        "avg_total_goals": away_season["avg_total_goals"],
        "avg_team_goals": away_season["avg_team_goals"],
        "avg_conceded": away_season["avg_conceded"],
        "btts_pct": away_season["btts_pct"],
        "over_1_5_pct": away_season["over_1_5_pct"],
        "over_2_5_pct": away_season["over_2_5_pct"],
        "over_3_5_pct": away_season["over_3_5_pct"],
        "clean_sheet_pct": away_season["clean_sheet_pct"],
        "failed_to_score_pct": away_season["failed_to_score_pct"],
        "avg_corners": None,
        "avg_cards": None
    }

    expected_goals = round(home_season["home_avg_goals_for"] + away_season["away_avg_goals_for"], 2)

    probabilities = {
        "over_1_5": round((home_stats["over_1_5_pct"] + away_stats["over_1_5_pct"]) / 2, 1),
        "over_2_5": round((home_stats["over_2_5_pct"] + away_stats["over_2_5_pct"]) / 2, 1),
        "over_3_5": round((home_stats["over_3_5_pct"] + away_stats["over_3_5_pct"]) / 2, 1),
        "btts": round((home_stats["btts_pct"] + away_stats["btts_pct"]) / 2, 1),
        "total_expected_goals": expected_goals,
        "expected_corners": None,
        "expected_cards": None
    }

    h2h_data = api_request(
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
            "home_wins": agg.get("homeTeam", {}).get("wins", 0),
            "away_wins": agg.get("awayTeam", {}).get("wins", 0),
            "draws": agg.get("homeTeam", {}).get("draws", 0),
            "home_goals": agg.get("homeTeam", {}).get("goals", 0),
            "away_goals": agg.get("awayTeam", {}).get("goals", 0),
            "total_matches": agg.get("numberOfMatches", 0)
        }

        for item in h2h_data.get("matches", [])[:5]:
            h2h_matches.append({
                "date": (item.get("utcDate") or "")[:10],
                "home": item.get("homeTeam", {}).get("name", ""),
                "away": item.get("awayTeam", {}).get("name", ""),
                "homeScore": item.get("score", {}).get("fullTime", {}).get("home"),
                "awayScore": item.get("score", {}).get("fullTime", {}).get("away"),
                "competition": item.get("competition", {}).get("name", "")
            })

    return {
        "match_info": {
            "home_team": home_team_data.get("name", home_team),
            "away_team": away_team_data.get("name", away_team),
            "home_short": home_team_data.get("shortName") or home_team_data.get("tla") or home_team_data.get("name", home_team)[:12],
            "away_short": away_team_data.get("shortName") or away_team_data.get("tla") or away_team_data.get("name", away_team)[:12],
            "home_logo": home_team_data.get("crest", home_logo) or home_logo,
            "away_logo": away_team_data.get("crest", away_logo) or away_logo,
            "home_formation": "",
            "away_formation": "",
            "home_coach": "",
            "away_coach": "",
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
        "h2h": {
            "matches": h2h_matches,
            "stats": h2h_stats
        },
        "probabilities": probabilities,
        "odds": {"home": 0, "draw": 0, "away": 0}
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
