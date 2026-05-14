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

app = FastAPI(title="TipFactory", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Footballdata.io configuration
API_KEY = os.environ.get('API_FOOTBALL_KEY', 'fd_7581f4cd968725edbafbc7b0f922c7a71fa6d3ce34fd4f63')
BASE_URL = "https://footballdata.io/api/v1"
HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

_cache = {}

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
        logger.info(f"API CALL: {url}")
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)

        if resp.status_code == 429:
            logger.error("RATE LIMIT alcanzado")
            return None
        if resp.status_code in [403, 401]:
            logger.error(f"AUTH ERROR {resp.status_code} - Verifica tu API key")
            return None
        if resp.status_code == 404:
            logger.error(f"NOT FOUND {endpoint}")
            return None

        resp.raise_for_status()
        data = resp.json()

        if not data.get('success'):
            logger.error(f"API error: {data.get('error', {}).get('message', 'Unknown')}")
            return None

        logger.info(f"API RESPONSE: OK")

        if cache_key:
            set_cache(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"API error en {endpoint}: {e}")
        return None

def format_match(m):
    """Convert footballdata.io match to our format"""
    home = m.get('home_team', {})
    away = m.get('away_team', {})
    league = m.get('league', {})

    # Status mapping
    status = m.get('status', 'scheduled')
    status_map = {
        'scheduled': 'NS', 'live': 'LIVE', 'in_play': '1H', 'halftime': 'HT',
        'finished': 'FT', 'postponed': 'PST', 'suspended': 'SUSP', 
        'cancelled': 'CANC', 'awarded': 'AWD'
    }

    # Extract date
    match_date = m.get('date', '')[:10] if m.get('date') else ''
    match_time = m.get('time', '')[:5] if m.get('time') else '--:--'

    return {
        "id": m.get('id'),
        "utcDate": m.get('date'),
        "matchDate": match_date,
        "status": status_map.get(status, status.upper()),
        "statusText": status,
        "minute": m.get('minute', 0),
        "venue": m.get('venue', ''),
        "matchday": m.get('matchday', 0),
        "homeTeam": {
            "id": home.get('id'),
            "name": home.get('name', 'Local'),
            "shortName": home.get('short_name', home.get('name', 'Local')[:15]),
            "crest": home.get('logo', ''),
        },
        "awayTeam": {
            "id": away.get('id'),
            "name": away.get('name', 'Visitante'),
            "shortName": away.get('short_name', away.get('name', 'Visitante')[:15]),
            "crest": away.get('logo', ''),
        },
        "competition": {
            "id": league.get('id'),
            "name": league.get('name', ''),
            "code": league.get('code', ''),
        },
        "league_name": league.get('name', ''),
        "country": league.get('country', ''),
        "homeScore": m.get('home_score'),
        "awayScore": m.get('away_score'),
        "halfTimeHome": m.get('half_time_home_score'),
        "halfTimeAway": m.get('half_time_away_score'),
    }

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/matches")
def matches(date: str = Query(None)):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"BUSCANDO PARTIDOS PARA: {date}")

    # Try exact date using /matches/date/{date}
    data = api_request(f'matches/date/{date}', cache_key=f"matches_{date}", ttl=300)

    if data and data.get('data'):
        matches_list = [format_match(m) for m in data['data']]
        logger.info(f"ENCONTRADOS {len(matches_list)} partidos en {date}")
        if matches_list:
            return {
                "matches": matches_list,
                "requested_date": date,
                "source_date": date,
                "is_exact": True
            }

    # Fallback: search nearby dates
    logger.info("Buscando en fechas cercanas...")
    for delta in [-1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6, -7, 7]:
        try:
            check_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")

            data = api_request(f'matches/date/{check_date}', cache_key=f"matches_{check_date}", ttl=300)

            if data and data.get('data'):
                matches_list = [format_match(m) for m in data['data']]
                if matches_list:
                    logger.info(f"ENCONTRADOS {len(matches_list)} partidos en fecha alternativa {check_date}")
                    return {
                        "matches": matches_list,
                        "requested_date": date,
                        "source_date": check_date,
                        "is_exact": False
                    }

        except Exception as e:
            logger.error(f"Error buscando {check_date}: {e}")
            continue

    logger.warning(f"NO HAY PARTIDOS para {date}")
    return {
        "matches": [],
        "requested_date": date,
        "source_date": None,
        "is_exact": True
    }

@app.get("/api/analyze/{match_id}")
def analyze(match_id: int):
    logger.info(f"ANALIZANDO PARTIDO {match_id}")

    # Get match details
    match_data = api_request(f'matches/{match_id}', cache_key=f"match_{match_id}", ttl=300)

    if not match_data or not match_data.get('data'):
        raise HTTPException(404, "Partido no encontrado")

    match_raw = match_data['data']
    match = format_match(match_raw)

    home_team = match_raw.get('home_team', {})
    away_team = match_raw.get('away_team', {})
    league = match_raw.get('league', {})

    home_id = home_team.get('id')
    away_id = away_team.get('id')
    league_id = league.get('id')
    season_id = match_raw.get('season_id')

    if not home_id or not away_id:
        raise HTTPException(500, "Datos del partido incompletos")

    # Get match stats
    stats_data = api_request(f'matches/{match_id}/stats', cache_key=f"match_stats_{match_id}", ttl=600)

    # Get match odds
    odds_data = api_request(f'matches/{match_id}/odds', cache_key=f"match_odds_{match_id}", ttl=600)

    # Get match probabilities
    prob_data = api_request(f'matches/{match_id}/probabilities', cache_key=f"match_prob_{match_id}", ttl=600)

    # H2H using teams endpoint
    h2h_data = api_request(f'teams/{home_id}/h2h/{away_id}', cache_key=f"h2h_{home_id}_{away_id}", ttl=3600)

    h2h_matches = []
    h2h_stats = {'home_wins': 0, 'away_wins': 0, 'draws': 0, 'total_matches': 0}

    if h2h_data and h2h_data.get('data'):
        h2h_list = h2h_data['data']
        h2h_stats['total_matches'] = len(h2h_list)

        for m in h2h_list[:5]:
            h2h_matches.append({
                'date': m.get('date', '')[:10],
                'home': m.get('home_team', {}).get('name', ''),
                'away': m.get('away_team', {}).get('name', ''),
                'homeScore': m.get('home_score'),
                'awayScore': m.get('away_score'),
                'competition': m.get('league', {}).get('name', '')
            })

            winner = m.get('winner')
            if winner == 'home':
                h2h_stats['home_wins'] += 1
            elif winner == 'away':
                h2h_stats['away_wins'] += 1
            else:
                h2h_stats['draws'] += 1

    # Team form (last 5 matches)
    def get_form(team_id):
        if not team_id:
            return []

        try:
            team_matches = api_request(f'teams/{team_id}/matches', {'limit': 5, 'status': 'finished'}, f"form_{team_id}", 1800)
        except Exception as e:
            logger.warning(f"Form fetch failed: {e}")
            return []

        form = []
        if not team_matches or not team_matches.get('data'):
            return form

        for m in team_matches['data'][:5]:
            is_home = m.get('home_team', {}).get('id') == team_id

            home_score = m.get('home_score', 0) or 0
            away_score = m.get('away_score', 0) or 0

            if is_home:
                tg, og = home_score, away_score
                winner = m.get('winner')
                if winner == 'home':
                    result = 'W'
                elif winner == 'away':
                    result = 'L'
                else:
                    result = 'D'
            else:
                tg, og = away_score, home_score
                winner = m.get('winner')
                if winner == 'away':
                    result = 'W'
                elif winner == 'home':
                    result = 'L'
                else:
                    result = 'D'

            form.append({
                'result': result,
                'result_text': 'Victoria' if result == 'W' else 'Derrota' if result == 'L' else 'Empate',
                'team_goals': tg,
                'opp_goals': og,
                'opponent': m.get('away_team', {}).get('name') if is_home else m.get('home_team', {}).get('name'),
                'venue': 'home' if is_home else 'away',
                'date': m.get('date', '')[:10],
                'competition': m.get('league', {}).get('name', '')
            })
        return form

    home_form = get_form(home_id)
    away_form = get_form(away_id)

    # Team stats
    def get_team_stats(team_id):
        if not team_id:
            return None
        try:
            stats = api_request(f'teams/{team_id}/stats', cache_key=f"team_stats_{team_id}", ttl=3600)
        except Exception as e:
            logger.warning(f"Team stats failed: {e}")
            return None

        if not stats or not stats.get('data'):
            return None
        return stats['data']

    home_stats_raw = get_team_stats(home_id)
    away_stats_raw = get_team_stats(away_id)

    # Extract stats safely
    def extract_stats(stats_raw):
        if not stats_raw:
            return {}
        return {
            'position': stats_raw.get('league_position', 0),
            'played': stats_raw.get('matches_played', 0),
            'won': stats_raw.get('wins', 0),
            'draw': stats_raw.get('draws', 0),
            'lost': stats_raw.get('losses', 0),
            'goals_for': stats_raw.get('goals_scored', 0),
            'goals_against': stats_raw.get('goals_conceded', 0),
            'points': stats_raw.get('points', 0),
            'form': stats_raw.get('form', '-----'),
            'avg_goals_scored': stats_raw.get('avg_goals_scored', 0),
            'avg_goals_conceded': stats_raw.get('avg_goals_conceded', 0),
            'avg_corners': stats_raw.get('avg_corners', 5.0),
            'avg_cards': stats_raw.get('avg_cards', 2.5),
        }

    home_standings = extract_stats(home_stats_raw)
    away_standings = extract_stats(away_stats_raw)

    # Calculate derived stats
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
        'position': home_standings.get('position', 0),
        'played': home_standings.get('played', home_calc['matches']),
        'won': home_standings.get('won', 0),
        'draw': home_standings.get('draw', 0),
        'lost': home_standings.get('lost', 0),
        'goals_for': home_standings.get('goals_for', home_calc['total_scored']),
        'goals_against': home_standings.get('goals_against', home_calc['total_conceded']),
        'points': home_standings.get('points', 0),
        'form_string': home_standings.get('form', ''),
        'avg_total_goals': round(home_calc['avg_scored'] + home_calc['avg_conceded'], 2),
        'avg_team_goals': home_calc['avg_scored'],
        'avg_conceded': home_calc['avg_conceded'],
        'btts_pct': calc_btts(home_form),
        'over_1_5_pct': calc_over(home_form, 1),
        'over_2_5_pct': calc_over(home_form, 2),
        'over_3_5_pct': calc_over(home_form, 3),
        'avg_corners': home_standings.get('avg_corners', 5.0),
        'avg_cards': home_standings.get('avg_cards', 2.5),
    }

    astats = {
        'position': away_standings.get('position', 0),
        'played': away_standings.get('played', away_calc['matches']),
        'won': away_standings.get('won', 0),
        'draw': away_standings.get('draw', 0),
        'lost': away_standings.get('lost', 0),
        'goals_for': away_standings.get('goals_for', away_calc['total_scored']),
        'goals_against': away_standings.get('goals_against', away_calc['total_conceded']),
        'points': away_standings.get('points', 0),
        'form_string': away_standings.get('form', ''),
        'avg_total_goals': round(away_calc['avg_scored'] + away_calc['avg_conceded'], 2),
        'avg_team_goals': away_calc['avg_scored'],
        'avg_conceded': away_calc['avg_conceded'],
        'btts_pct': calc_btts(away_form),
        'over_1_5_pct': calc_over(away_form, 1),
        'over_2_5_pct': calc_over(away_form, 2),
        'over_3_5_pct': calc_over(away_form, 3),
        'avg_corners': away_standings.get('avg_corners', 4.5),
        'avg_cards': away_standings.get('avg_cards', 2.3),
    }

    over_1_5 = round((hstats['over_1_5_pct'] + astats['over_1_5_pct']) / 2, 1)
    over_2_5 = round((hstats['over_2_5_pct'] + astats['over_2_5_pct']) / 2, 1)
    over_3_5 = round((hstats['over_3_5_pct'] + astats['over_3_5_pct']) / 2, 1)
    btts = round((hstats['btts_pct'] + astats['btts_pct']) / 2, 1)
    xg = round(hstats['avg_team_goals'] + astats['avg_team_goals'], 2)
    corners = round((hstats['avg_corners'] + astats['avg_corners']) * 0.9, 1)
    cards = round(hstats['avg_cards'] + astats['avg_cards'], 1)

    # Extract odds if available
    odds = {"home": 0, "draw": 0, "away": 0}
    if odds_data and odds_data.get('data'):
        odds_raw = odds_data['data']
        if isinstance(odds_raw, list) and len(odds_raw) > 0:
            first_odds = odds_raw[0]
            odds = {
                "home": first_odds.get('home_odds', 0),
                "draw": first_odds.get('draw_odds', 0),
                "away": first_odds.get('away_odds', 0)
            }

    return {
        "match_info": {
            "home_team": home_team.get('name', 'Local'),
            "away_team": away_team.get('name', 'Visitante'),
            "home_short": home_team.get('short_name', home_team.get('name', 'Local')[:12]),
            "away_short": away_team.get('short_name', away_team.get('name', 'Visitante')[:12]),
            "home_logo": home_team.get('logo', ''),
            "away_logo": away_team.get('logo', ''),
            "home_formation": '',
            "away_formation": '',
            "home_coach": '',
            "away_coach": '',
            "league": league.get('name', ''),
            "country": league.get('country', ''),
            "date": match.get('matchDate', 'N/A'),
            "time": match.get('utcDate', '')[11:16] if match.get('utcDate') else '--:--',
            "venue": match.get('venue', ''),
            "status": match_raw.get('status', 'scheduled'),
            "minute": match.get('minute', 0),
            "matchday": match.get('matchday', ''),
            "home_score": match.get('homeScore'),
            "away_score": match.get('awayScore'),
            "halfTimeHome": match.get('halfTimeHome'),
            "halfTimeAway": match.get('halfTimeAway'),
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
        "odds": odds,
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "cache_size": len(_cache),
        "time": datetime.now().isoformat(),
        "api_key": "configured" if API_KEY else "missing",
        "api_provider": "footballdata.io"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
