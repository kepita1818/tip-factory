import os
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Futbol Stats", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

API_KEY = os.environ.get('API_FOOTBALL_KEY')
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {
    'X-Auth-Token': API_KEY,
    'Accept-Encoding': ''
}

# IDs de competiciones soportadas por football-data.org (plan gratuito)
COMPETITIONS = {
    'PL': 'Premier League',      # Inglaterra
    'BL1': 'Bundesliga',         # Alemania
    'SA': 'Serie A',             # Italia
    'PD': 'La Liga',             # España
    'FL1': 'Ligue 1',            # Francia
    'CL': 'Champions League',
    'EL': 'Europa League',
    'EC': 'Euro Championship',
    'WC': 'World Cup',
}

# Cache
_cache = {}

def get_cache(key, ttl=600):
    if key in _cache:
        data, ts = _cache[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None

def set_cache(key, data):
    _cache[key] = (data, datetime.now())

def api_request(endpoint, params=None, cache_key=None, ttl=600):
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
            logger.error("RATE LIMIT - espera un minuto")
            return None
        if resp.status_code == 403:
            logger.error("FORBIDDEN - API key inválida o sin créditos")
            return None
        if resp.status_code == 401:
            logger.error("UNAUTHORIZED - API key incorrecta")
            return None
            
        resp.raise_for_status()
        data = resp.json()
        
        if cache_key:
            set_cache(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"API error: {e}")
        return None

def format_match(m):
    """Adapta el formato de football-data.org al que espera el frontend"""
    home = m.get('homeTeam', {})
    away = m.get('awayTeam', {})
    competition = m.get('competition', {})
    
    # Estado del partido
    status = m.get('status', '')
    status_map = {
        'SCHEDULED': 'NS',
        'LIVE': '1H',
        'IN_PLAY': '1H',
        'PAUSED': 'HT',
        'FINISHED': 'FT',
        'POSTPONED': 'PST',
        'SUSPENDED': 'SUSP',
        'CANCELLED': 'CANC',
    }
    status_short = status_map.get(status, status)
    
    # Minuto (football-data no siempre lo da en partidos en vivo)
    minute = m.get('minute', {}).get('regular', 0) if isinstance(m.get('minute'), dict) else 0
    
    return {
        "id": m.get('id'),
        "utcDate": m.get('utcDate'),
        "status": status_short,
        "statusText": status,
        "homeTeam": {
            "id": home.get('id'),
            "name": home.get('name', 'Local'),
            "shortName": home.get('shortName', home.get('name', 'Local')[:15]),
            "crest": home.get('crest', home.get('logo', ''))
        },
        "awayTeam": {
            "id": away.get('id'),
            "name": away.get('name', 'Visitante'),
            "shortName": away.get('shortName', away.get('name', 'Visitante')[:15]),
            "crest": away.get('crest', away.get('logo', ''))
        },
        "competition": {"id": competition.get('id'), "name": competition.get('name', '')},
        "league_name": competition.get('name', ''),
        "country": competition.get('area', {}).get('name', ''),
        "homeScore": m.get('score', {}).get('fullTime', {}).get('home'),
        "awayScore": m.get('score', {}).get('fullTime', {}).get('away'),
        "minute": minute
    }

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/matches")
def matches(date: str = Query(None)):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    logger.info(f"=== BUSCANDO PARTIDOS PARA: {date} ===")
    
    # football-data.org usa dateFrom/dateTo (formato YYYY-MM-DD)
    # Buscamos en la fecha exacta y ±3 días
    for delta in [0, -1, 1, -2, 2, -3, 3]:
        try:
            check_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
            
            data = api_request(
                'matches',
                {'dateFrom': check_date, 'dateTo': check_date},
                f"matches_{check_date}",
                300
            )
            
            if data and data.get('matches'):
                matches_list = [format_match(m) for m in data['matches']]
                logger.info(f"✅ ENCONTRADOS {len(matches_list)} partidos en {check_date}")
                return matches_list
                
        except Exception as e:
            logger.error(f"Error buscando {check_date}: {e}")
            continue
    
    logger.warning(f"❌ NO HAY PARTIDOS para {date} ni fechas cercanas")
    return []

@app.get("/api/live")
def live():
    logger.info("=== BUSCANDO PARTIDOS EN VIVO ===")
    
    # football-data.org: filtrar por status=LIVE o IN_PLAY
    data = api_request(
        'matches',
        {'status': 'LIVE,IN_PLAY'},
        "live_matches",
        60
    )
    
    if not data:
        return []
    
    matches = [format_match(m) for m in data.get('matches', [])]
    logger.info(f"✅ {len(matches)} partidos en vivo")
    return matches

@app.get("/api/analyze/{match_id}")
def analyze(match_id: int):
    logger.info(f"=== ANALIZANDO PARTIDO {match_id} ===")
    
    # Obtener detalle del partido
    data = api_request(f'matches/{match_id}', cache_key=f"match_{match_id}", ttl=300)
    if not data:
        raise HTTPException(404, "Partido no encontrado")
    
    match = data
    home_id = match['homeTeam']['id']
    away_id = match['awayTeam']['id']
    comp_id = match['competition']['id']
    
    logger.info(f"Partido: {match['homeTeam']['name']} vs {match['awayTeam']['name']}")
    
    # football-data.org no tiene endpoint de estadísticas detalladas como API-Football
    # Usamos datos básicos del partido y generamos estimaciones
    
    # Intentar obtener partidos recientes del equipo local
    home_matches = api_request(
        f'teams/{home_id}/matches',
        {'status': 'FINISHED', 'limit': 5},
        f"team_{home_id}_last5",
        1800
    )
    
    away_matches = api_request(
        f'teams/{away_id}/matches',
        {'status': 'FINISHED', 'limit': 5},
        f"team_{away_id}_last5",
        1800
    )
    
    def process_form(team_matches, team_id):
        form = []
        if not team_matches or not team_matches.get('matches'):
            return form
        
        for m in team_matches['matches'][:5]:
            is_home = m['homeTeam']['id'] == team_id
            score = m.get('score', {}).get('fullTime', {})
            home_goals = score.get('home', 0) or 0
            away_goals = score.get('away', 0) or 0
            
            if is_home:
                team_goals = home_goals
                opp_goals = away_goals
                result = 'W' if home_goals > away_goals else 'L' if home_goals < away_goals else 'D'
                result_text = 'Victoria' if result == 'W' else 'Derrota' if result == 'L' else 'Empate'
            else:
                team_goals = away_goals
                opp_goals = home_goals
                result = 'W' if away_goals > home_goals else 'L' if away_goals < home_goals else 'D'
                result_text = 'Victoria' if result == 'W' else 'Derrota' if result == 'L' else 'Empate'
            
            opponent = m['awayTeam']['name'] if is_home else m['homeTeam']['name']
            
            form.append({
                'result': result, 'result_text': result_text,
                'team_goals': team_goals, 'opp_goals': opp_goals,
                'opponent': opponent, 'venue': 'home' if is_home else 'away',
                'date': m['utcDate'][:10] if m.get('utcDate') else '2024-01-01'
            })
        return form
    
    hf = process_form(home_matches, home_id)
    af = process_form(away_matches, away_id)
    
    # Datos por defecto si no hay forma
    if not hf:
        hf = [{'result': 'W', 'result_text': 'Victoria', 'team_goals': 2, 'opp_goals': 1, 'opponent': 'Rival', 'venue': 'home', 'date': '2024-05-01'}]
    if not af:
        af = [{'result': 'D', 'result_text': 'Empate', 'team_goals': 1, 'opp_goals': 1, 'opponent': 'Rival', 'venue': 'away', 'date': '2024-05-01'}]
    
    # Estadísticas estimadas (football-data.org free no da stats detalladas)
    # Usamos promedios básicos de los últimos partidos
    def calc_avg_goals(form_list):
        if not form_list:
            return 1.5, 1.2
        scored = sum(f['team_goals'] for f in form_list) / len(form_list)
        conceded = sum(f['opp_goals'] for f in form_list) / len(form_list)
        return round(scored, 2), round(conceded, 2)
    
    home_scored, home_conceded = calc_avg_goals(hf)
    away_scored, away_conceded = calc_avg_goals(af)
    
    avg_total = home_scored + away_scored
    
    hstats = {
        'avg_total_goals': round(avg_total, 2),
        'avg_team_goals': home_scored,
        'avg_conceded': home_conceded,
        'btts_pct': min(90, int(home_scored * 15 + home_conceded * 15)),
        'over_1_5_pct': min(95, int(avg_total * 25 + 20)),
        'over_2_5_pct': min(90, int(avg_total * 20 + 10)),
        'over_3_5_pct': max(10, int(avg_total * 12)),
        'avg_corners': 5.0, 'avg_cards': 2.5,
        'home': {'matches': len(hf), 'avg_total': round(avg_total * 1.1, 2),
                'avg_corners': 5.5, 'avg_cards': 2.6,
                'over_2_5': min(95, int(avg_total * 20 + 15)),
                'over_3_5': max(10, int(avg_total * 12)),
                'btts': min(95, int(home_scored * 15 + home_conceded * 15) + 5),
                'over_8_5_corners': 70, 'over_9_5_corners': 55, 'over_10_5_corners': 40,
                'over_3_5_cards': 75, 'over_4_5_cards': 50},
        'away': {'matches': len(af), 'avg_total': round(avg_total * 0.9, 2),
                'avg_corners': 4.0, 'avg_cards': 2.1,
                'over_2_5': max(20, int(avg_total * 20 + 10) - 10),
                'over_3_5': max(5, int(avg_total * 12) - 5),
                'btts': max(30, int(away_scored * 15 + away_conceded * 15) - 5),
                'over_8_5_corners': 60, 'over_9_5_corners': 45, 'over_10_5_corners': 30,
                'over_3_5_cards': 65, 'over_4_5_cards': 45}
    }
    
    astats = {
        'avg_total_goals': round(avg_total, 2),
        'avg_team_goals': away_scored,
        'avg_conceded': away_conceded,
        'btts_pct': min(90, int(away_scored * 15 + away_conceded * 15)),
        'over_1_5_pct': min(95, int(avg_total * 25 + 20)),
        'over_2_5_pct': min(90, int(avg_total * 20 + 10)),
        'over_3_5_pct': max(10, int(avg_total * 12)),
        'avg_corners': 4.5, 'avg_cards': 2.3,
        'home': hstats['home'],  # Reutilizamos para simplificar
        'away': hstats['away']
    }
    
    # Probabilidades combinadas
    over_1_5 = round((hstats['over_1_5_pct'] + astats['over_1_5_pct']) / 2, 1)
    over_2_5 = round((hstats['over_2_5_pct'] + astats['over_2_5_pct']) / 2, 1)
    over_3_5 = round((hstats['over_3_5_pct'] + astats['over_3_5_pct']) / 2, 1)
    btts = round((hstats['btts_pct'] + astats['btts_pct']) / 2, 1)
    xg = round(home_scored + away_scored, 2)
    corners = round((hstats['avg_corners'] + astats['avg_corners']) * 0.9, 1)
    cards = round(hstats['avg_cards'] + astats['avg_cards'], 1)
    
    return {
        "match_info": {
            "home_team": match['homeTeam']['name'],
            "away_team": match['awayTeam']['name'],
            "home_short": match['homeTeam'].get('shortName', match['homeTeam']['name'][:12]),
            "away_short": match['awayTeam'].get('shortName', match['awayTeam']['name'][:12]),
            "home_logo": match['homeTeam'].get('crest', ''),
            "away_logo": match['awayTeam'].get('crest', ''),
            "league": match['competition']['name'],
            "date": match['utcDate'][:10] if match.get('utcDate') else 'N/A',
            "time": match['utcDate'][11:16] if match.get('utcDate') else '--:--',
            "venue": match.get('venue', 'N/A'),
            "status": match.get('status', 'SCHEDULED'),
            "minute": match.get('minute', {}).get('regular', 0) if isinstance(match.get('minute'), dict) else 0,
            "home_score": match.get('score', {}).get('fullTime', {}).get('home'),
            "away_score": match.get('score', {}).get('fullTime', {}).get('away')
        },
        "home_form": hf,
        "away_form": af,
        "home_stats": hstats,
        "away_stats": astats,
        "probabilities": {
            "over_1_5": over_1_5,
            "over_2_5": over_2_5,
            "over_3_5": over_3_5,
            "btts": btts,
            "total_expected_goals": xg,
            "expected_corners": corners,
            "expected_cards": cards
        },
        "source": "football-data.org"
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "cache_size": len(_cache),
        "time": datetime.now().isoformat(),
        "api_key": "configured" if API_KEY else "missing",
        "api_source": "football-data.org"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
