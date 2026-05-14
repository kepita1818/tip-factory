import os
import logging
from datetime import datetime, timedelta

import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TipFactory", version="1.0.0")

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
    "EC": "Euro Cup",
    "WC": "World Cup"
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
            logger.error("RATE LIMIT")
            return None
        if resp.status_code in (401, 403):
            logger.error(f"AUTH ERROR {resp.status_code}")
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
        "homeScore": ft.get("home"),
        "awayScore": ft.get("away"),
        "halfTimeHome": ht.get("home"),
        "halfTimeAway": ht.get("away")
    }


def dedupe_matches(matches):
    unique = []
    seen = set()

    for m in matches:
        if not m.get("id"):
            continue
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)

    return unique


def get_team_form(team_id, comp_code=None):
    if not team_id:
        return []

    params = {"status": "FINISHED", "limit": 5}
    if comp_code:
        params["competitions"] = comp_code

    data = api_request(
        f"teams/{team_id}/matches",
        params=params,
        cache_key=f"form_{team_id}_{comp_code}",
        ttl=1800
    )

    form = []
    if not data or not data.get("matches"):
        return form

    for m in data["matches"][:5]:
        home = m.get("homeTeam", {})
        away = m.get("awayTeam", {})
        score = m.get("score", {}).get("fullTime", {})
        hg = score.get("home", 0) or 0
        ag = score.get("away", 0) or 0
        is_home = home.get("id") == team_id

        if is_home:
            tg = hg
            og = ag
            opponent = away.get("name", "Rival")
        else:
            tg = ag
            og = hg
            opponent = home.get("name", "Rival")

        result = "D"
        if tg > og:
            result = "W"
        elif tg < og:
            result = "L"

        form.append({
            "result": result,
            "result_text": "Victoria" if result == "W" else "Empate" if result == "D" else "Derrota",
            "team_goals": tg,
            "opp_goals": og,
            "opponent": opponent,
            "venue": "home" if is_home else "away",
            "date": (m.get("utcDate") or "")[:10],
            "competition": m.get("competition", {}).get("name", "")
        })

    return form


def get_team_standings(team_id, comp_code, season_year):
    if not team_id or not comp_code:
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
            team = row.get("team", {})
            if team.get("id") == team_id:
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


def calc_from_form(form_list):
    if not form_list:
        return {
            "avg_scored": 0,
            "avg_conceded": 0,
            "matches": 0,
            "total_scored": 0,
            "total_conceded": 0
        }

    scored = sum(x["team_goals"] for x in form_list)
    conceded = sum(x["opp_goals"] for x in form_list)
    matches = len(form_list)

    return {
        "avg_scored": round(scored / matches, 2),
        "avg_conceded": round(conceded / matches, 2),
        "matches": matches,
        "total_scored": scored,
        "total_conceded": conceded
    }


def calc_over(form_list, threshold):
    if not form_list:
        return 0
    count = sum(1 for x in form_list if (x["team_goals"] + x["opp_goals"]) > threshold)
    return round((count / len(form_list)) * 100)


def calc_btts(form_list):
    if not form_list:
        return 0
    count = sum(1 for x in form_list if x["team_goals"] > 0 and x["opp_goals"] > 0)
    return round((count / len(form_list)) * 100)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/matches")
def matches(date: str = Query(None)):
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    logger.info(f"BUSCANDO PARTIDOS PARA: {date}")

    all_matches = []
    found_competitions = set()

    general_data = api_request(
        "matches",
        params={"dateFrom": date, "dateTo": date},
        cache_key=f"matches_{date}",
        ttl=300
    )

    if general_data and general_data.get("matches"):
        general_matches = [format_match(m) for m in general_data["matches"]]
        general_matches = [m for m in general_matches if m["matchDate"] == date]
        all_matches.extend(general_matches)
        logger.info(f"/matches general: {len(general_matches)} partidos")

    for comp_code, comp_name in TOP_COMPETITIONS.items():
        try:
            data = api_request(
                f"competitions/{comp_code}/matches",
                params={"dateFrom": date, "dateTo": date},
                cache_key=f"comp_{comp_code}_{date}",
                ttl=600
            )

            if data and data.get("matches"):
                comp_matches = [format_match(m) for m in data["matches"]]
                comp_matches = [m for m in comp_matches if m["matchDate"] == date]
                if comp_matches:
                    all_matches.extend(comp_matches)
                    found_competitions.add(comp_name)
                    logger.info(f"{comp_name}: {len(comp_matches)} partidos")
        except Exception as e:
            logger.error(f"Error en {comp_name}: {e}")

    unique_matches = dedupe_matches(all_matches)

    if unique_matches:
        return {
            "matches": unique_matches,
            "requested_date": date,
            "source_date": date,
            "is_exact": True,
            "competitions_found": list(found_competitions)
        }

    logger.info("Buscando en fechas cercanas...")

    for delta in [-1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6, -7, 7]:
        try:
            check_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
            fallback_matches = []

            data = api_request(
                "matches",
                params={"dateFrom": check_date, "dateTo": check_date},
                cache_key=f"matches_{check_date}",
                ttl=300
            )

            if data and data.get("matches"):
                general_matches = [format_match(m) for m in data["matches"]]
                general_matches = [m for m in general_matches if m["matchDate"] == check_date]
                fallback_matches.extend(general_matches)

            for comp_code, comp_name in TOP_COMPETITIONS.items():
                comp_data = api_request(
                    f"competitions/{comp_code}/matches",
                    params={"dateFrom": check_date, "dateTo": check_date},
                    cache_key=f"comp_{comp_code}_{check_date}",
                    ttl=600
                )

                if comp_data and comp_data.get("matches"):
                    comp_matches = [format_match(m) for m in comp_data["matches"]]
                    comp_matches = [m for m in comp_matches if m["matchDate"] == check_date]
                    fallback_matches.extend(comp_matches)

            unique_fallback = dedupe_matches(fallback_matches)

            if unique_fallback:
                logger.info(f"ENCONTRADOS {len(unique_fallback)} partidos en fecha alternativa {check_date}")
                return {
                    "matches": unique_fallback,
                    "requested_date": date,
                    "source_date": check_date,
                    "is_exact": False,
                    "competitions_found": list(found_competitions)
                }
        except Exception as e:
            logger.error(f"Error buscando {check_date}: {e}")

    logger.warning(f"NO HAY PARTIDOS para {date}")
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
        logger.warning(f"No se pudo obtener matches/{match_id}, usando fallback")
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
                "avg_corners": 5.0,
                "avg_cards": 2.5
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
                "avg_corners": 4.5,
                "avg_cards": 2.3
            },
            "h2h": {
                "matches": [],
                "stats": {
                    "home_wins": 0,
                    "away_wins": 0,
                    "draws": 0,
                    "home_goals": 0,
                    "away_goals": 0,
                    "total_matches": 0
                }
            },
            "probabilities": {
                "over_1_5": 0,
                "over_2_5": 0,
                "over_3_5": 0,
                "btts": 0,
                "total_expected_goals": 0,
                "expected_corners": 9.5,
                "expected_cards": 4.8
            },
            "odds": {"home": 0, "draw": 0, "away": 0}
        }

    home_team_data = match.get("homeTeam", {}) or {}
    away_team_data = match.get("awayTeam", {}) or {}
    competition = match.get("competition", {}) or {}
    area = match.get("area", {}) or competition.get("area", {}) or {}
    season = match.get("season", {}) or {}
    season_year = (season.get("startDate") or "2025")[:4]
    comp_code = competition.get("code")

    home_id = home_team_data.get("id")
    away_id = away_team_data.get("id")
    match_detail = format_match(match)

    home_form = get_team_form(home_id, comp_code)
    away_form = get_team_form(away_id, comp_code)

    home_standings = get_team_standings(home_id, comp_code, season_year)
    away_standings = get_team_standings(away_id, comp_code, season_year)

    home_calc = calc_from_form(home_form)
    away_calc = calc_from_form(away_form)

    home_stats = {
        "position": home_standings["position"] if home_standings else 0,
        "played": home_standings["played"] if home_standings else home_calc["matches"],
        "won": home_standings["won"] if home_standings else 0,
        "draw": home_standings["draw"] if home_standings else 0,
        "lost": home_standings["lost"] if home_standings else 0,
        "goals_for": home_standings["goals_for"] if home_standings else home_calc["total_scored"],
        "goals_against": home_standings["goals_against"] if home_standings else home_calc["total_conceded"],
        "points": home_standings["points"] if home_standings else 0,
        "form_string": home_standings["form"] if home_standings else "",
        "avg_total_goals": round(home_calc["avg_scored"] + home_calc["avg_conceded"], 2),
        "avg_team_goals": home_calc["avg_scored"],
        "avg_conceded": home_calc["avg_conceded"],
        "btts_pct": calc_btts(home_form),
        "over_1_5_pct": calc_over(home_form, 1),
        "over_2_5_pct": calc_over(home_form, 2),
        "over_3_5_pct": calc_over(home_form, 3),
        "avg_corners": 5.0,
        "avg_cards": 2.5
    }

    away_stats = {
        "position": away_standings["position"] if away_standings else 0,
        "played": away_standings["played"] if away_standings else away_calc["matches"],
        "won": away_standings["won"] if away_standings else 0,
        "draw": away_standings["draw"] if away_standings else 0,
        "lost": away_standings["lost"] if away_standings else 0,
        "goals_for": away_standings["goals_for"] if away_standings else away_calc["total_scored"],
        "goals_against": away_standings["goals_against"] if away_standings else away_calc["total_conceded"],
        "points": away_standings["points"] if away_standings else 0,
        "form_string": away_standings["form"] if away_standings else "",
        "avg_total_goals": round(away_calc["avg_scored"] + away_calc["avg_conceded"], 2),
        "avg_team_goals": away_calc["avg_scored"],
        "avg_conceded": away_calc["avg_conceded"],
        "btts_pct": calc_btts(away_form),
        "over_1_5_pct": calc_over(away_form, 1),
        "over_2_5_pct": calc_over(away_form, 2),
        "over_3_5_pct": calc_over(away_form, 3),
        "avg_corners": 4.5,
        "avg_cards": 2.3
    }

    probabilities = {
        "over_1_5": round((home_stats["over_1_5_pct"] + away_stats["over_1_5_pct"]) / 2, 1),
        "over_2_5": round((home_stats["over_2_5_pct"] + away_stats["over_2_5_pct"]) / 2, 1),
        "over_3_5": round((home_stats["over_3_5_pct"] + away_stats["over_3_5_pct"]) / 2, 1),
        "btts": round((home_stats["btts_pct"] + away_stats["btts_pct"]) / 2, 1),
        "total_expected_goals": round(home_stats["avg_team_goals"] + away_stats["avg_team_goals"], 2),
        "expected_corners": round((home_stats["avg_corners"] + away_stats["avg_corners"]) * 0.9, 1),
        "expected_cards": round(home_stats["avg_cards"] + away_stats["avg_cards"], 1)
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
            "minute": match_detail.get("minute", 0),
            "matchday": match_detail.get("matchday", 0),
            "home_score": match_detail.get("homeScore"),
            "away_score": match_detail.get("awayScore"),
            "halfTimeHome": match_detail.get("halfTimeHome"),
            "halfTimeAway": match_detail.get("halfTimeAway")
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
