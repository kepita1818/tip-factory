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

app = FastAPI(title="TipFactory", version="9.0.0")

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

_cache = {}

TOP_COMPETITIONS = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "CL": "Champions League",
    "EL": "Europa League",
    "EC": "European Championship",
    "PPL": "Primeira Liga",
    "DED": "Eredivisie",
    "BSA": "Serie A Brazil",
    "CLI": "Copa Libertadores",
    "SD": "Segunda Division"
}

LEAGUE_CODE_MAP = {
    "la liga": "PD",
    "laliga": "PD",
    "primera division": "PD",
    "spanish primera division": "PD",
    "spain la liga": "PD",
    "segunda division": "SD",
    "laliga 2": "SD",
    "premier league": "PL",
    "bundesliga": "BL1",
    "serie a": "SA",
    "ligue 1": "FL1",
    "primeira liga": "PPL",
    "eredivisie": "DED",
    "champions league": "CL",
    "uefa champions league": "CL",
    "europa league": "EL",
    "uefa europa league": "EL",
    "campeonato brasileiro série a": "BSA",
    "campeonato brasileiro serie a": "BSA",
    "serie a brazil": "BSA",
    "copa libertadores": "CLI"
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
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)

        if resp.status_code == 429:
            logger.error("RATE LIMIT")
            return None
        if resp.status_code in [401, 403]:
            logger.error(f"AUTH ERROR {resp.status_code}")
            return None
        if resp.status_code == 404:
            logger.error(f"NOT FOUND {endpoint}")
            return None

        resp.raise_for_status()
        data = resp.json()

        if cache_key:
            set_cache(cache_key, data)

        return data
    except Exception as e:
        logger.error(f"API error en {endpoint}: {e}")
        return None


def safe_get(d, *keys, default=None):
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def normalize_name(name):
    if not name:
        return ""
    text = str(name).strip().lower()
    replacements = {
        " cf": "",
        " fc": "",
        " sad": "",
        " club de futbol": "",
        " de futbol": "",
        " fútbol": " futbol",
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        ".": "",
        ",": "",
        "-": " ",
        "_": " ",
        "  ": " "
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def format_match(m):
    home = m.get("homeTeam", {}) or {}
    away = m.get("awayTeam", {}) or {}
    competition = m.get("competition", {}) or {}
    score = m.get("score", {}) or {}
    ft = score.get("fullTime", {}) if isinstance(score, dict) else {}
    ht = score.get("halfTime", {}) if isinstance(score, dict) else {}
    match_date = m.get("utcDate", "")[:10] if m.get("utcDate") else ""

    status = m.get("status", "SCHEDULED")
    status_map = {
        "SCHEDULED": "NS",
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
        "utcDate": m.get("utcDate"),
        "matchDate": match_date,
        "status": status_map.get(status, status),
        "statusText": status,
        "minute": minute,
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
        "country": safe_get(m, "area", "name", default="") or safe_get(competition, "area", "name", default=""),
        "homeScore": ft.get("home") if isinstance(ft, dict) else None,
        "awayScore": ft.get("away") if isinstance(ft, dict) else None,
        "halfTimeHome": ht.get("home") if isinstance(ht, dict) else None,
        "halfTimeAway": ht.get("away") if isinstance(ht, dict) else None
    }


def get_fdorg_competitions():
    data = api_request("competitions", cache_key="all_competitions", ttl=86400)
    if not data or not isinstance(data, dict):
        return []
    return data.get("competitions", [])


def resolve_competition(league_name, country_name=""):
    comps = get_fdorg_competitions()
    target_league = normalize_name(league_name)
    target_country = normalize_name(country_name)

    mapped_code = LEAGUE_CODE_MAP.get(target_league)
    if mapped_code:
        for comp in comps:
            if comp.get("code") == mapped_code:
                area_name = normalize_name(safe_get(comp, "area", "name", default=""))
                if not target_country or area_name == target_country or mapped_code in ["CL", "EL", "EC", "CLI"]:
                    return {
                        "id": comp.get("id"),
                        "code": comp.get("code"),
                        "name": comp.get("name")
                    }

    for comp in comps:
        comp_name = normalize_name(comp.get("name", ""))
        comp_code = comp.get("code", "")
        area_name = normalize_name(safe_get(comp, "area", "name", default=""))

        if comp_name == target_league:
            if not target_country or area_name == target_country:
                return {
                    "id": comp.get("id"),
                    "code": comp_code,
                    "name": comp.get("name")
                }

    return None


def find_team_id(team_name, competition_id=None):
    if not team_name:
        return None

    target = normalize_name(team_name)

    if competition_id:
        comp_data = api_request(
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

    data = api_request("teams", params={"limit": 500}, cache_key="all_teams_500", ttl=86400)
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

    data = api_request(
        f"teams/{team_id}/matches",
        params=params,
        cache_key=f"team_matches_{team_id}_{competition_id}_{limit}",
        ttl=1800
    )

    matches = data.get("matches", []) if isinstance(data, dict) else []

    if not matches:
        data = api_request(
            f"teams/{team_id}/matches",
            params={"status": "FINISHED", "limit": limit},
            cache_key=f"team_matches_fallback_{team_id}_{limit}",
            ttl=1800
        )
        matches = data.get("matches", []) if isinstance(data, dict) else []

    return matches


def get_standings(team_id, competition_id, season_year):
    if not competition_id:
        return None

    data = api_request(
        f"competitions/{competition_id}/standings",
        {"season": season_year},
        f"standings_{competition_id}_{season_year}",
        3600
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


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/matches")
def matches(date: str = Query(None)):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"BUSCANDO PARTIDOS PARA: {date}")

    all_matches = []
    found_competitions = set()

    for comp_code, comp_name in TOP_COMPETITIONS.items():
        try:
            data = api_request(
                f"competitions/{comp_code}/matches",
                {"dateFrom": date, "dateTo": date},
                f"comp_{comp_code}_{date}",
                600
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
            continue

    if not all_matches:
        logger.info("No se encontraron partidos en competiciones individuales, probando /matches general")
        try:
            data = api_request(
                "matches",
                {"dateFrom": date, "dateTo": date},
                f"matches_{date}",
                300
            )

            if data and data.get("matches"):
                general_matches = [format_match(m) for m in data["matches"]]
                general_matches = [m for m in general_matches if m["matchDate"] == date]
                all_matches.extend(general_matches)
                logger.info(f"/matches general: {len(general_matches)} partidos")
        except Exception as e:
            logger.error(f"Error en /matches general: {e}")

    seen_ids = set()
    unique_matches = []
    for m in all_matches:
        if m["id"] not in seen_ids:
            seen_ids.add(m["id"])
            unique_matches.append(m)

    logger.info(f"TOTAL: {len(unique_matches)} partidos unicos en {date}")

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

            for comp_code, comp_name in TOP_COMPETITIONS.items():
                data = api_request(
                    f"competitions/{comp_code}/matches",
                    {"dateFrom": check_date, "dateTo": check_date},
                    f"comp_{comp_code}_{check_date}",
                    600
                )
                if data and data.get("matches"):
                    comp_matches = [format_match(m) for m in data["matches"]]
                    comp_matches = [m for m in comp_matches if m["matchDate"] == check_date]
                    fallback_matches.extend(comp_matches)

            if fallback_matches:
                seen_fb = set()
                unique_fallback = []
                for m in fallback_matches:
                    if m["id"] not in seen_fb:
                        seen_fb.add(m["id"])
                        unique_fallback.append(m)

                return {
                    "matches": unique_fallback,
                    "requested_date": date,
                    "source_date": check_date,
                    "is_exact": False,
                    "competitions_found": list(found_competitions)
                }

        except Exception as e:
            logger.error(f"Error buscando {check_date}: {e}")
            continue

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
    home_team: str = Query(None),
    away_team: str = Query(None),
    home_logo: str = Query(""),
    away_logo: str = Query(""),
    league: str = Query(""),
    date: str = Query(""),
    time: str = Query("--:--"),
    country: str = Query(""),
    venue: str = Query("")
):
    logger.info(f"ANALIZANDO PARTIDO {match_id}")

    match_data = api_request(f"matches/{match_id}", cache_key=f"match_{match_id}", ttl=300)
    if not match_data:
        raise HTTPException(404, "Partido no encontrado")

    match = match_data
    match_detail = format_match(match)

    real_home_name = safe_get(match, "homeTeam", "name", default="Local")
    real_away_name = safe_get(match, "awayTeam", "name", default="Visitante")
    real_league = safe_get(match, "competition", "name", default="")
    real_country = safe_get(match, "area", "name", default="") or safe_get(match, "competition", "area", "name", default="")
    comp_id = safe_get(match, "competition", "id", default=None)
    season = match.get("season", {}) or {}
    season_year = int(season.get("startDate", "2025-01-01")[:4])

    resolved_competition = None
    if comp_id:
        resolved_competition = {
            "id": comp_id,
            "code": safe_get(match, "competition", "code", default=""),
            "name": real_league
        }
    else:
        resolved_competition = resolve_competition(real_league, real_country)

    home_id = safe_get(match, "homeTeam", "id", default=None)
    away_id = safe_get(match, "awayTeam", "id", default=None)

    if not home_id and home_team:
        home_id = find_team_id(home_team, resolved_competition["id"] if resolved_competition else None)
    if not away_id and away_team:
        away_id = find_team_id(away_team, resolved_competition["id"] if resolved_competition else None)

    h2h_data = api_request(f"matches/{match_id}/head2head", {"limit": 10}, f"h2h_{match_id}", 3600)
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

    competition_id = resolved_competition["id"] if resolved_competition else None

    home_recent = get_team_recent_matches(home_id, competition_id, 10)
    away_recent = get_team_recent_matches(away_id, competition_id, 10)

    home_standings = get_standings(home_id, competition_id, season_year) if home_id and competition_id else None
    away_standings = get_standings(away_id, competition_id, season_year) if away_id and competition_id else None

    home_form, home_stats = build_form_and_stats(home_id, home_recent, home_standings)
    away_form, away_stats = build_form_and_stats(away_id, away_recent, away_standings)

    probabilities = {
        "over_1_5": round((home_stats["over_1_5_pct"] + away_stats["over_1_5_pct"]) / 2, 1) if (home_stats["played"] and away_stats["played"]) else 0.0,
        "over_2_5": round((home_stats["over_2_5_pct"] + away_stats["over_2_5_pct"]) / 2, 1) if (home_stats["played"] and away_stats["played"]) else 0.0,
        "over_3_5": round((home_stats["over_3_5_pct"] + away_stats["over_3_5_pct"]) / 2, 1) if (home_stats["played"] and away_stats["played"]) else 0.0,
        "btts": round((home_stats["btts_pct"] + away_stats["btts_pct"]) / 2, 1) if (home_stats["played"] and away_stats["played"]) else 0.0,
        "total_expected_goals": round(home_stats["avg_team_goals"] + away_stats["avg_team_goals"], 2) if (home_stats["played"] and away_stats["played"]) else 0,
        "home_xg": 0,
        "away_xg": 0
    }

    return JSONResponse({
        "match_info": {
            "home_team": real_home_name,
            "away_team": real_away_name,
            "home_short": safe_get(match, "homeTeam", "shortName", default=real_home_name[:12]),
            "away_short": safe_get(match, "awayTeam", "shortName", default=real_away_name[:12]),
            "home_logo": home_logo or safe_get(match, "homeTeam", "crest", default=""),
            "away_logo": away_logo or safe_get(match, "awayTeam", "crest", default=""),
            "league": real_league,
            "country": real_country,
            "date": (match.get("utcDate") or "")[:10] or date,
            "time": (match.get("utcDate") or "")[11:16] or time,
            "venue": match.get("venue", "") or venue,
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
        "odds": {
            "home": 0,
            "draw": 0,
            "away": 0
        },
        "stats_available": bool(home_stats["played"] or away_stats["played"]),
        "debug": {
            "match_id": match_id,
            "competition": resolved_competition,
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
        "cache_size": len(_cache),
        "time": datetime.now().isoformat(),
        "api_key": "configured" if API_KEY else "missing",
        "version": "9.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
