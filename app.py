import os
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import json

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
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

API_KEY = os.environ.get('API_FOOTBALL_KEY', '')
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {
    'X-Auth-Token': API_KEY,
}

_cache = {}

# Top competitions to query individually
TOP_COMPETITIONS = {
    'PL': 'Premier League',
    'PD': 'La Liga', 
    'SA': 'Serie A',
    'BL1': 'Bundesliga',
    'FL1': 'Ligue 1',
    'CL': 'Champions League',
    'EL': 'Europa League',
    'EC': 'European Championship',
    'PPL': 'Primeira Liga',
    'DED': 'Eredivisie',
    'BSA': 'Serie A Brazil',
    'CLI': 'Copa Libertadores',
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
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)

        if resp.status_code == 429:
            logger.error("RATE LIMIT")
            return None
        if resp.status_code in [403, 401]:
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

def format_match(m):
    home = m.get('homeTeam', {})
    away = m.get('awayTeam', {})
    competition = m.get('competition', {})
    score = m.get('score', {})
    ft = score.get('fullTime', {}) if isinstance(score, dict) else {}
    ht = score.get('halfTime', {}) if isinstance(score, dict) else {}
    match_date = m.get('utcDate', '')[:10] if m.get('utcDate') else ''

    status = m.get('status', 'SCHEDULED')
    status_map = {
        'SCHEDULED': 'NS', 'LIVE': 'LIVE', 'IN_PLAY': '1H', 'PAUSED': 'HT',
        'FINISHED': 'FT', 'POSTPONED': 'PST', 'SUSPENDED': 'SUSP', 
        'CANCELLED': 'CANC', 'AWARDED': 'AWD'
    }

    minute = m.get('minute', 0)
    if isinstance(minute, dict):
        minute = minute.get('regular', 0)

    return {
        "id": m.get('id'),
        "utcDate": m.get('utcDate'),
        "matchDate": match_date,
        "status": status_map.get(status, status),
        "statusText": status,
        "minute": minute,
        "venue": m.get('venue', ''),
        "matchday": m.get('matchday', 0),
        "homeTeam": {
            "id": home.get('id'),
            "name": home.get('name', 'Local'),
            "shortName": home.get('shortName', home.get('name', 'Local')[:15]),
            "crest": home.get('crest', ''),
        },
        "awayTeam": {
            "id": away.get('id'),
            "name": away.get('name', 'Visitante'),
            "shortName": away.get('shortName', away.get('name', 'Visitante')[:15]),
            "crest": away.get('crest', ''),
        },
        "competition": {
            "id": competition.get('id'),
            "name": competition.get('name', ''),
            "code": competition.get('code', ''),
        },
        "league_name": competition.get('name', ''),
        "country": m.get('area', {}).get('name', '') if m.get('area') else competition.get('area', {}).get('name', ''),
        "homeScore": ft.get('home') if isinstance(ft, dict) else None,
        "awayScore": ft.get('away') if isinstance(ft, dict) else None,
        "halfTimeHome": ht.get('home') if isinstance(ht, dict) else None,
        "halfTimeAway": ht.get('away') if isinstance(ht, dict) else None,
    }

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

    # Strategy 1: Query each top competition individually
    for comp_code, comp_name in TOP_COMPETITIONS.items():
        try:
            data = api_request(
                f'competitions/{comp_code}/matches',
                {'dateFrom': date, 'dateTo': date},
                f"comp_{comp_code}_{date}",
                600
            )

            if data and data.get('matches'):
                comp_matches = [format_match(m) for m in data['matches']]
                # Filter to ensure they're actually on the requested date
                comp_matches = [m for m in comp_matches if m['matchDate'] == date]
                if comp_matches:
                    all_matches.extend(comp_matches)
                    found_competitions.add(comp_name)
                    logger.info(f"  {comp_name}: {len(comp_matches)} partidos")

        except Exception as e:
            logger.error(f"Error en {comp_name}: {e}")
            continue

    # Strategy 2: Also try the general /matches endpoint as fallback
    if not all_matches:
        logger.info("No se encontraron partidos en competiciones individuales, probando /matches general")
        try:
            data = api_request(
                'matches',
                {'dateFrom': date, 'dateTo': date},
                f"matches_{date}",
                300
            )
            if data and data.get('matches'):
                general_matches = [format_match(m) for m in data['matches']]
                general_matches = [m for m in general_matches if m['matchDate'] == date]
                all_matches.extend(general_matches)
                logger.info(f"  /matches general: {len(general_matches)} partidos")
        except Exception as e:
            logger.error(f"Error en /matches general: {e}")

    # Remove duplicates by match ID
    seen_ids = set()
    unique_matches = []
    for m in all_matches:
        if m['id'] not in seen_ids:
            seen_ids.add(m['id'])
            unique_matches.append(m)

    logger.info(f"TOTAL: {len(unique_matches)} partidos unicos en {date}")
    logger.info(f"Competiciones encontradas: {', '.join(found_competitions) if found_competitions else 'Ninguna'}")

    if unique_matches:
        return {
            "matches": unique_matches,
            "requested_date": date,
            "source_date": date,
            "is_exact": True,
            "competitions_found": list(found_competitions)
        }

    # Fallback: search nearby dates
    logger.info("Buscando en fechas cercanas...")
    for delta in [-1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6, -7, 7]:
        try:
            check_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
            fallback_matches = []

            for comp_code, comp_name in TOP_COMPETITIONS.items():
                data = api_request(
                    f'competitions/{comp_code}/matches',
                    {'dateFrom': check_date, 'dateTo': check_date},
                    f"comp_{comp_code}_{check_date}",
                    600
                )
                if data and data.get('matches'):
                    comp_matches = [format_match(m) for m in data['matches']]
                    comp_matches = [m for m in comp_matches if m['matchDate'] == check_date]
                    fallback_matches.extend(comp_matches)

            if fallback_matches:
                seen_ids = set()
                unique_fallback = []
                for m in fallback_matches:
                    if m['id'] not in seen_ids:
                        seen_ids.add(m['id'])
                        unique_fallback.append(m)

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
            continue

    logger.warning(f"NO HAY PARTIDOS para {date}")
    return {
        "matches": [],
        "requested_date": date,
        "source_date": None,
        "is_exact": True,
        "competitions_found": []
    }

@app.get("/api/analyze/{match_id}")
def analyze(match_id: int):
    logger.info(f"ANALIZANDO PARTIDO {match_id}")

    # Strategy 1: Try the general /matches/{id} endpoint
    data = api_request(f'matches/{match_id}', cache_key=f"match_{match_id}", ttl=300)

    # Strategy 2: If general endpoint fails, search in cached competition data
    if not data:
        logger.warning(f"Match {match_id} not in general endpoint, searching cache...")
        found_match = None
        found_comp = None

        for cache_key in list(_cache.keys()):
            if cache_key.startswith('comp_'):
                cached_data = get_cache(cache_key)
                if cached_data and cached_data.get('matches'):
                    for m in cached_data['matches']:
                        if m.get('id') == match_id:
                            found_match = m
                            # Extract competition code from cache key (comp_PD_2026-05-14)
                            parts = cache_key.split('_')
                            if len(parts) >= 2:
                                found_comp = parts[1]
                            logger.info(f"Found match {match_id} in cache: {cache_key}")
                            break
                if found_match:
                    break

        if found_match:
            data = found_match
            logger.info(f"Using cached match data for {match_id}")
        else:
            logger.error(f"Match {match_id} not found anywhere")
            raise HTTPException(404, "Partido no encontrado. Puede que no esté disponible con tu plan API gratuito.")

    # Now process the match data
    match = data

    # Safely extract IDs with fallbacks
    home_team = match.get('homeTeam', {})
    away_team = match.get('awayTeam', {})
    competition = match.get('competition', {})

    home_id = home_team.get('id')
    away_id = away_team.get('id')
    comp_id = competition.get('id')

    if not home_id or not away_id:
        logger.error(f"Missing team IDs for match {match_id}")
        raise HTTPException(500, "Datos del partido incompletos")

    season = match.get('season', {})
    season_year = season.get('startDate', '')[:4] if season.get('startDate') else '2025'

    match_detail = format_match(match)

    # H2H - with error handling
    h2h_data = None
    try:
        h2h_data = api_request(f'matches/{match_id}/head2head', {'limit': 10}, f"h2h_{match_id}", 3600)
    except Exception as e:
        logger.warning(f"H2H fetch failed for {match_id}: {e}")

    h2h_matches = []
    h2h_stats = {'home_wins': 0, 'away_wins': 0, 'draws': 0, 'home_goals': 0, 'away_goals': 0, 'total_matches': 0}

    if h2h_data and h2h_data.get('aggregates'):
        agg = h2h_data['aggregates']
        h2h_stats = {
            'home_wins': agg.get('homeTeam', {}).get('wins', 0),
            'away_wins': agg.get('awayTeam', {}).get('wins', 0),
            'draws': agg.get('homeTeam', {}).get('draws', 0),
            'home_goals': agg.get('homeTeam', {}).get('goals', 0),
            'away_goals': agg.get('awayTeam', {}).get('goals', 0),
            'total_matches': agg.get('numberOfMatches', 0)
        }
        for m in h2h_data.get('matches', [])[:5]:
            h2h_matches.append({
                'date': m.get('utcDate', '')[:10],
                'home': m['homeTeam']['name'],
                'away': m['awayTeam']['name'],
                'homeScore': m.get('score', {}).get('fullTime', {}).get('home'),
                'awayScore': m.get('score', {}).get('fullTime', {}).get('away'),
                'competition': m['competition']['name']
            })

    # FORMA - with error handling
    def get_form(team_id, comp_id=None):
        if not team_id:
            return []
        params = {'status': 'FINISHED', 'limit': 5}
        if comp_id:
            params['competitions'] = comp_id

        try:
            team_matches = api_request(f'teams/{team_id}/matches', params, f"form_{team_id}_{comp_id}", 1800)
        except Exception as e:
            logger.warning(f"Form fetch failed for team {team_id}: {e}")
            return []

        form = []
        if not team_matches or not team_matches.get('matches'):
            return form

        for m in team_matches['matches'][:5]:
            is_home = m['homeTeam']['id'] == team_id
            score = m.get('score', {}).get('fullTime', {})
            hg = score.get('home', 0) or 0
            ag = score.get('away', 0) or 0

            if is_home:
                tg, og, result = hg, ag, 'W' if hg > ag else 'L' if hg < ag else 'D'
            else:
                tg, og, result = ag, hg, 'W' if ag > hg else 'L' if ag < hg else 'D'

            form.append({
                'result': result,
                'result_text': 'Victoria' if result == 'W' else 'Derrota' if result == 'L' else 'Empate',
                'team_goals': tg, 'opp_goals': og,
                'opponent': m['awayTeam']['name'] if is_home else m['homeTeam']['name'],
                'venue': 'home' if is_home else 'away',
                'date': m['utcDate'][:10] if m.get('utcDate') else '2024-01-01',
                'competition': m['competition']['name']
            })
        return form

    home_form = get_form(home_id, comp_id)
    away_form = get_form(away_id, comp_id)

    # STANDINGS - with error handling
    def get_standings(team_id, comp_id, season_year):
        if not comp_id:
            return None
        try:
            stats_data = api_request(f'competitions/{comp_id}/standings', {'season': season_year}, f"standings_{comp_id}_{season_year}", 3600)
        except Exception as e:
            logger.warning(f"Standings fetch failed: {e}")
            return None

        if not stats_data or not stats_data.get('standings'):
            return None

        for standing in stats_data['standings']:
            for table in standing.get('table', []):
                if table['team']['id'] == team_id:
                    return {
                        'position': table.get('position', 0),
                        'played': table.get('playedGames', 0),
                        'won': table.get('won', 0),
                        'draw': table.get('draw', 0),
                        'lost': table.get('lost', 0),
                        'goals_for': table.get('goalsFor', 0),
                        'goals_against': table.get('goalsAgainst', 0),
                        'points': table.get('points', 0),
                        'form': table.get('form', '-----')
                    }
        return None

    home_standings = get_standings(home_id, comp_id, season_year)
    away_standings = get_standings(away_id, comp_id, season_year)

    # STATS calculation
    def calc_from_form(form_list):
        if not form_list:
            return {'avg_scored': 1.5, 'avg_conceded': 1.2, 'matches': 0, 'total_scored': 0, 'total_conceded': 0}
        scored = sum(f['team_goals'] for f in form_list)
        conceded = sum(f['opp_goals'] for f in form_list)
        matches = len(form_list)
        return {
            'avg_scored': round(scored / matches, 2),
            'avg_conceded': round(conceded / matches, 2),
            'matches': matches,
            'total_scored': scored,
            'total_conceded': conceded
        }

    def calc_over(form_list, threshold):
        if not form_list: return 50
        return round((sum(1 for f in form_list if (f['team_goals'] + f['opp_goals']) > threshold) / len(form_list)) * 100)

    def calc_btts(form_list):
        if not form_list: return 50
        return round((sum(1 for f in form_list if f['team_goals'] > 0 and f['opp_goals'] > 0) / len(form_list)) * 100)

    home_calc = calc_from_form(home_form)
    away_calc = calc_from_form(away_form)

    hstats = {
        'position': home_standings.get('position', 0) if home_standings else 0,
        'played': home_standings.get('played', 0) if home_standings else home_calc['matches'],
        'won': home_standings.get('won', 0) if home_standings else 0,
        'draw': home_standings.get('draw', 0) if home_standings else 0,
        'lost': home_standings.get('lost', 0) if home_standings else 0,
        'goals_for': home_standings.get('goals_for', 0) if home_standings else home_calc['total_scored'],
        'goals_against': home_standings.get('goals_against', 0) if home_standings else home_calc['total_conceded'],
        'points': home_standings.get('points', 0) if home_standings else 0,
        'form_string': home_standings.get('form', '') if home_standings else '',
        'avg_total_goals': round(home_calc['avg_scored'] + home_calc['avg_conceded'], 2),
        'avg_team_goals': home_calc['avg_scored'],
        'avg_conceded': home_calc['avg_conceded'],
        'btts_pct': calc_btts(home_form),
        'over_1_5_pct': calc_over(home_form, 1),
        'over_2_5_pct': calc_over(home_form, 2),
        'over_3_5_pct': calc_over(home_form, 3),
        'avg_corners': 5.0,
        'avg_cards': 2.5,
    }

    astats = {
        'position': away_standings.get('position', 0) if away_standings else 0,
        'played': away_standings.get('played', 0) if away_standings else away_calc['matches'],
        'won': away_standings.get('won', 0) if away_standings else 0,
        'draw': away_standings.get('draw', 0) if away_standings else 0,
        'lost': away_standings.get('lost', 0) if away_standings else 0,
        'goals_for': away_standings.get('goals_for', 0) if away_standings else away_calc['total_scored'],
        'goals_against': away_standings.get('goals_against', 0) if away_standings else away_calc['total_conceded'],
        'points': away_standings.get('points', 0) if away_standings else 0,
        'form_string': away_standings.get('form', '') if away_standings else '',
        'avg_total_goals': round(away_calc['avg_scored'] + away_calc['avg_conceded'], 2),
        'avg_team_goals': away_calc['avg_scored'],
        'avg_conceded': away_calc['avg_conceded'],
        'btts_pct': calc_btts(away_form),
        'over_1_5_pct': calc_over(away_form, 1),
        'over_2_5_pct': calc_over(away_form, 2),
        'over_3_5_pct': calc_over(away_form, 3),
        'avg_corners': 4.5,
        'avg_cards': 2.3,
    }

    over_1_5 = round((hstats['over_1_5_pct'] + astats['over_1_5_pct']) / 2, 1)
    over_2_5 = round((hstats['over_2_5_pct'] + astats['over_2_5_pct']) / 2, 1)
    over_3_5 = round((hstats['over_3_5_pct'] + astats['over_3_5_pct']) / 2, 1)
    btts = round((hstats['btts_pct'] + astats['btts_pct']) / 2, 1)
    xg = round(hstats['avg_team_goals'] + astats['avg_team_goals'], 2)
    corners = round((hstats['avg_corners'] + astats['avg_corners']) * 0.9, 1)
    cards = round(hstats['avg_cards'] + astats['avg_cards'], 1)

    return {
        "match_info": {
            "home_team": home_team.get('name', 'Local'),
            "away_team": away_team.get('name', 'Visitante'),
            "home_short": home_team.get('shortName', home_team.get('name', 'Local')[:12]),
            "away_short": away_team.get('shortName', away_team.get('name', 'Visitante')[:12]),
            "home_logo": home_team.get('crest', ''),
            "away_logo": away_team.get('crest', ''),
            "home_formation": home_team.get('formation', ''),
            "away_formation": away_team.get('formation', ''),
            "home_coach": home_team.get('coach', {}).get('name', ''),
            "away_coach": away_team.get('coach', {}).get('name', ''),
            "league": competition.get('name', ''),
            "country": match.get('area', {}).get('name', '') if match.get('area') else competition.get('area', {}).get('name', ''),
            "date": match.get('utcDate', '')[:10] if match.get('utcDate') else 'N/A',
            "time": match.get('utcDate', '')[11:16] if match.get('utcDate') else '--:--',
            "venue": match.get('venue', ''),
            "status": match.get('status', 'SCHEDULED'),
            "minute": match_detail.get('minute', 0),
            "matchday": match_detail.get('matchday', 0),
            "home_score": match_detail.get('homeScore'),
            "away_score": match_detail.get('awayScore'),
            "halfTimeHome": match_detail.get('halfTimeHome'),
            "halfTimeAway": match_detail.get('halfTimeAway'),
        },
        "home_form": home_form,
        "away_form": away_form,
        "home_stats": hstats,
        "away_stats": astats,
        "h2h": {"matches": h2h_matches, "stats": h2h_stats},
        "probabilities": {
            "over_1_5": over_1_5,
            "over_2_5": over_2_5,
            "over_3_5": over_3_5,
            "btts": btts,
            "total_expected_goals": xg,
            "expected_corners": corners,
            "expected_cards": cards
        },
        "odds": {"home": 0, "draw": 0, "away": 0},
    }

@app.get("/health")")
def health():
    return {
        "status": "ok",
        "cache_size": len(_cache),
        "time": datetime.now().isoformat(),
        "api_key": "configured" if API_KEY else "missing",
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
