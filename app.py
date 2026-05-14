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

# Footballdata.io configuration - EXACT URL from dashboard
API_KEY = os.environ.get('API_FOOTBALL_KEY', 'fd_7581f4cd968725edbafbc7b0f922c7a71fa6d3ce34fd4f63')
BASE_URL = "https://footballdata.io/api/v1"
HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
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
            logger.error(f"AUTH ERROR {resp.status_code}")
            return None
        if resp.status_code == 404:
            logger.error(f"NOT FOUND {endpoint}")
            return None

        resp.raise_for_status()
        data = resp.json()
        logger.info(f"API RESPONSE: {data.get('status', 'unknown')}")

        if cache_key:
            set_cache(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"API error en {endpoint}: {e}")
        return None

def format_fixture(f):
    """Convert footballdata.io fixture to our format"""
    home = f.get('home_team', {})
    away = f.get('away_team', {})
    league = f.get('league', {})

    status = f.get('status', 'scheduled')
    status_map = {
        'scheduled': 'NS', 'live': 'LIVE', 'in_play': '1H', 'halftime': 'HT',
        'finished': 'FT', 'postponed': 'PST', 'suspended': 'SUSP', 
        'cancelled': 'CANC', 'awarded': 'AWD'
    }

    match_date = ''
    if f.get('match_date'):
        match_date = f['match_date'][:10]
    elif f.get('date'):
        match_date = f['date'][:10]

    return {
        "id": f.get('match_id') or f.get('id'),
        "utcDate": f.get('match_date') or f.get('date'),
        "matchDate": match_date,
        "status": status_map.get(status, status.upper()),
        "statusText": status,
        "minute": f.get('minute', 0),
        "venue": f.get('venue', ''),
        "matchday": f.get('matchday', 0),
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
            "id": league.get('id') or league.get('league_id'),
            "name": league.get('name', ''),
            "code": league.get('code', ''),
        },
        "league_name": league.get('name', ''),
        "country": league.get('country', ''),
        "homeScore": f.get('home_score'),
        "awayScore": f.get('away_score'),
        "halfTimeHome": f.get('half_time_home_score'),
        "halfTimeAway": f.get('half_time_away_score'),
    }

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/matches")
def matches(date: str = Query(None)):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"BUSCANDO PARTIDOS PARA: {date}")

    # Use /fixtures?date=YYYY-MM-DD
    data = api_request('fixtures', {'date': date}, cache_key=f"fixtures_{date}", ttl=300)

    if data and data.get('data'):
        fixtures = [format_fixture(f) for f in data['data']]
        logger.info(f"ENCONTRADOS {len(fixtures)} partidos en {date}")
        if fixtures:
            return {
                "matches": fixtures,
                "requested_date": date,
                "source_date": date,
                "is_exact": True
            }

    # Fallback: search nearby dates
    logger.info("Buscando en fechas cercanas...")
    for delta in [-1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6, -7, 7]:
        try:
            check_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")

            data = api_request('fixtures', {'date': check_date}, cache_key=f"fixtures_{check_date}", ttl=300)

            if data and data.get('data'):
                fixtures = [format_fixture(f) for f in data['data']]
                if fixtures:
                    logger.info(f"ENCONTRADOS {len(fixtures)} partidos en fecha alternativa {check_date}")
                    return {
                        "matches": fixtures,
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
    match_data = api_request(f'match/{match_id}', cache_key=f"match_{match_id}", ttl=300)

    if not match_data or not match_data.get('data'):
        raise HTTPException(404, "Partido no encontrado")

    match_raw = match_data['data']
    match = format_fixture(match_raw)

    home_team = match_raw.get('home_team', {})
    away_team = match_raw.get('away_team', {})
    league = match_raw.get('league', {})

    home_id = home_team.get('id')
    away_id = away_team.get('id')

    if not home_id or not away_id:
        raise HTTPException(500, "Datos del partido incompletos")

    # Get match stats
    stats_data = api_request(f'match/{match_id}/stats', cache_key=f"match_stats_{match_id}", ttl=600)

    # Get match odds
    odds_data = api_request(f'match/{match_id}/odds', cache_key=f"match_odds_{match_id}", ttl=600)

    # Get H2H
    h2h_data = api_request('h2h', {'team_a': home_id, 'team_b': away_id}, cache_key=f"h2h_{home_id}_{away_id}", ttl=3600)

    h2h_matches = []
    h2h_stats = {'home_wins': 0, 'away_wins': 0, 'draws': 0, 'total_matches': 0}

    if h2h_data and h2h_data.get('data'):
        h2h_list = h2h_data['data']
        h2h_stats['total_matches'] = len(h2h_list)

        for m in h2h_list[:5]:
            h2h_matches.append({
                'date': m.get('match_date', '')[:10] if m.get('match_date') else '',
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

    # Team form
    def get_form(team_id):
        if not team_id:
            return []

        try:
            team_matches = api_request('fixtures', {'team_id': team_id, 'status': 'finished', 'limit': 5}, f"form_{team_id}", 1800)
        except Exception as e:
            logger.warning(f"Form fetch failed: {e}")
            return []

        form = []
        if not team_matches or not team_matches.get('data'):
            return form

        for f in team_matches['data'][:5]:
            is_home = f.get('home_team', {}).get('id') == team_id

            home_score = f.get('home_score', 0) or 0
            away_score = f.get('away_score', 0) or 0

            if is_home:
                tg, og = home_score, away_score
                winner = f.get('winner')
                if winner == 'home':
                    result = 'W'
                elif winner == 'away':
                    result = 'L'
                else:
                    result = 'D'
            else:
                tg, og = away_score, home_score
                winner = f.get('winner')
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
                'opponent': f.get('away_team', {}).get('name') if is_home else f.get('home_team', {}).get('name'),
                'venue': 'home' if is_home else 'away',
                'date': f.get('match_date', '')[:10] if f.get('match_date') else '',
                'competition': f.get('league', {}).get('name', '')
            })
        return form

    home_form = get_form(home_id)
    away_form = get_form(away_id)

    # Calculate stats
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
        'position': 0,
        'played': home_calc['matches'],
        'won': sum(1 for f in home_form if f['result'] == 'W'),
        'draw': sum(1 for f in home_form if f['result'] == 'D'),
        'lost': sum(1 for f in home_form if f['result'] == 'L'),
        'goals_for': home_calc['total_scored'],
        'goals_against': home_calc['total_conceded'],
        'points': 0,
        'form_string': ''.join(f['result'] for f in home_form),
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
        'position': 0,
        'played': away_calc['matches'],
        'won': sum(1 for f in away_form if f['result'] == 'W'),
        'draw': sum(1 for f in away_form if f['result'] == 'D'),
        'lost': sum(1 for f in away_form if f['result'] == 'L'),
        'goals_for': away_calc['total_scored'],
        'goals_against': away_calc['total_conceded'],
        'points': 0,
        'form_string': ''.join(f['result'] for f in away_form),
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

    # Extract odds
    odds = {"home": 0, "draw": 0, "away": 0}
    if odds_data and odds_data.get('data'):
        odds_raw = odds_data['data']
        if isinstance(odds_raw, dict):
            odds = {
                "home": odds_raw.get('home_odds', 0),
                "draw": odds_raw.get('draw_odds', 0),
                "away": odds_raw.get('away_odds', 0)
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
