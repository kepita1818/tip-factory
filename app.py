import os
import json
import logging
import requests
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ============ CONFIGURACION ============
API_FOOTBALL_KEY = os.environ.get('API_FOOTBALL_KEY', '650c819e61df3915394dd45ba62df836')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8883372208:AAEqL3nx6g14ULVsOSx_zN23b9OHptTMNq4')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
USE_DEMO_MODE = os.environ.get('USE_DEMO_MODE', 'false').lower() == 'true'

API_BASE_URL = 'https://v3.football.api-sports.io'
HEADERS = {
    'x-rapidapi-key': API_FOOTBALL_KEY,
    'x-rapidapi-host': 'v3.football.api-sports.io'
}

# Temporada actual
CURRENT_SEASON = 2025

# Ligas soportadas
ALL_LEAGUES = {
    140: {'name': 'La Liga', 'country': 'Spain', 'filter': 'Spain'},
    39: {'name': 'Premier League', 'country': 'England', 'filter': 'England'},
    135: {'name': 'Serie A', 'country': 'Italy', 'filter': 'Italy'},
    78: {'name': 'Bundesliga', 'country': 'Germany', 'filter': 'Germany'},
    61: {'name': 'Ligue 1', 'country': 'France', 'filter': 'France'},
    2: {'name': 'Champions League', 'country': 'World', 'filter': 'Europe'},
    3: {'name': 'Europa League', 'country': 'World', 'filter': 'Europe'},
    848: {'name': 'Conference League', 'country': 'World', 'filter': 'Europe'},
    88: {'name': 'Eredivisie', 'country': 'Netherlands', 'filter': 'Europe'},
    94: {'name': 'Primeira Liga', 'country': 'Portugal', 'filter': 'Europe'},
}

# Demo teams for fallback
DEMO_TEAMS = {
    'Spain': [
        ('Real Madrid', 'https://media.api-sports.io/football/teams/541.png'),
        ('Barcelona', 'https://media.api-sports.io/football/teams/529.png'),
        ('Atletico Madrid', 'https://media.api-sports.io/football/teams/530.png'),
        ('Sevilla', 'https://media.api-sports.io/football/teams/536.png'),
        ('Real Sociedad', 'https://media.api-sports.io/football/teams/548.png'),
        ('Valencia', 'https://media.api-sports.io/football/teams/532.png'),
        ('Villarreal', 'https://media.api-sports.io/football/teams/533.png'),
        ('Athletic Bilbao', 'https://media.api-sports.io/football/teams/531.png'),
    ],
    'England': [
        ('Manchester City', 'https://media.api-sports.io/football/teams/50.png'),
        ('Arsenal', 'https://media.api-sports.io/football/teams/42.png'),
        ('Liverpool', 'https://media.api-sports.io/football/teams/40.png'),
        ('Chelsea', 'https://media.api-sports.io/football/teams/49.png'),
        ('Manchester United', 'https://media.api-sports.io/football/teams/33.png'),
        ('Tottenham', 'https://media.api-sports.io/football/teams/47.png'),
        ('Newcastle', 'https://media.api-sports.io/football/teams/34.png'),
        ('Aston Villa', 'https://media.api-sports.io/football/teams/66.png'),
    ],
    'Italy': [
        ('Inter', 'https://media.api-sports.io/football/teams/505.png'),
        ('AC Milan', 'https://media.api-sports.io/football/teams/489.png'),
        ('Juventus', 'https://media.api-sports.io/football/teams/496.png'),
        ('Napoli', 'https://media.api-sports.io/football/teams/492.png'),
        ('Roma', 'https://media.api-sports.io/football/teams/497.png'),
        ('Lazio', 'https://media.api-sports.io/football/teams/487.png'),
        ('Atalanta', 'https://media.api-sports.io/football/teams/499.png'),
        ('Fiorentina', 'https://media.api-sports.io/football/teams/502.png'),
    ],
    'Germany': [
        ('Bayern Munich', 'https://media.api-sports.io/football/teams/157.png'),
        ('Borussia Dortmund', 'https://media.api-sports.io/football/teams/165.png'),
        ('RB Leipzig', 'https://media.api-sports.io/football/teams/173.png'),
        ('Bayer Leverkusen', 'https://media.api-sports.io/football/teams/168.png'),
        ('Eintracht Frankfurt', 'https://media.api-sports.io/football/teams/169.png'),
        ('Wolfsburg', 'https://media.api-sports.io/football/teams/161.png'),
        ('Stuttgart', 'https://media.api-sports.io/football/teams/172.png'),
        ('Freiburg', 'https://media.api-sports.io/football/teams/160.png'),
    ],
    'France': [
        ('PSG', 'https://media.api-sports.io/football/teams/85.png'),
        ('Marseille', 'https://media.api-sports.io/football/teams/81.png'),
        ('Lyon', 'https://media.api-sports.io/football/teams/80.png'),
        ('Monaco', 'https://media.api-sports.io/football/teams/91.png'),
        ('Lille', 'https://media.api-sports.io/football/teams/79.png'),
        ('Nice', 'https://media.api-sports.io/football/teams/84.png'),
        ('Rennes', 'https://media.api-sports.io/football/teams/94.png'),
        ('Lens', 'https://media.api-sports.io/football/teams/93.png'),
    ],
    'Europe': [
        ('Real Madrid', 'https://media.api-sports.io/football/teams/541.png'),
        ('Manchester City', 'https://media.api-sports.io/football/teams/50.png'),
        ('Bayern Munich', 'https://media.api-sports.io/football/teams/157.png'),
        ('Inter', 'https://media.api-sports.io/football/teams/505.png'),
        ('PSG', 'https://media.api-sports.io/football/teams/85.png'),
        ('Arsenal', 'https://media.api-sports.io/football/teams/42.png'),
        ('Barcelona', 'https://media.api-sports.io/football/teams/529.png'),
        ('Dortmund', 'https://media.api-sports.io/football/teams/165.png'),
    ]
}

# ============ LOGGING ============
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ FLASK APP ============
app = Flask(__name__, static_folder='static', template_folder='templates')

# ============ CACHE ============
cache = {}

def get_cache(key, max_age=1800):
    if key in cache:
        data, timestamp = cache[key]
        if (datetime.now() - timestamp).seconds < max_age:
            return data
    return None

def set_cache(key, data):
    cache[key] = (data, datetime.now())

# ============ DEMO DATA GENERATOR ============
def generate_demo_matches(date_str, league_filter='all'):
    """Genera partidos de demo cuando la API falla"""
    matches = []
    match_id_base = int(datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y%m%d'))

    leagues_to_use = []
    if league_filter == 'all':
        leagues_to_use = list(DEMO_TEAMS.keys())
    elif league_filter in DEMO_TEAMS:
        leagues_to_use = [league_filter]
    else:
        leagues_to_use = list(DEMO_TEAMS.keys())

    hour = 14
    for league in leagues_to_use:
        teams = DEMO_TEAMS[league]
        # Generar 3-4 partidos por liga
        num_matches = min(4, len(teams) // 2)
        for i in range(num_matches):
            home_team = teams[i * 2]
            away_team = teams[i * 2 + 1]
            match_id = match_id_base + (list(ALL_LEAGUES.keys())[list(ALL_LEAGUES.values()).index(next(l for l in ALL_LEAGUES.values() if l['filter'] == league))] * 100) + i

            time_str = f"{hour:02d}:00"
            hour += 2
            if hour > 22:
                hour = 14

            league_info = next((v for v in ALL_LEAGUES.values() if v['filter'] == league), {'name': league, 'country': league})

            matches.append({
                'id': match_id,
                'utcDate': f"{date_str}T{time_str}:00+00:00",
                'status': 'NS',
                'homeTeam': {
                    'id': match_id + 1,
                    'name': home_team[0],
                    'shortName': home_team[0][:15],
                    'crest': home_team[1]
                },
                'awayTeam': {
                    'id': match_id + 2,
                    'name': away_team[0],
                    'shortName': away_team[0][:15],
                    'crest': away_team[1]
                },
                'competition': {'id': 0, 'name': league_info['name']},
                'league_name': league_info['name'],
                'country': league_info['country'],
                'filter': league
            })

    return matches

# ============ API FOOTBALL ============
def api_request(endpoint, params=None):
    if USE_DEMO_MODE:
        return {'response': []}

    cache_key = f"{endpoint}:{json.dumps(params or {})}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    url = f"{API_BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if response.status_code == 429:
            logger.warning("Rate limit alcanzado")
            return {'response': [], 'errors': ['Rate limit reached']}
        response.raise_for_status()
        data = response.json()
        set_cache(cache_key, data)
        return data
    except requests.exceptions.Timeout:
        logger.error("API Timeout")
        return {'response': [], 'errors': ['API timeout']}
    except requests.exceptions.ConnectionError:
        logger.error("API Connection Error")
        return {'response': [], 'errors': ['API connection error']}
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {'response': [], 'errors': [str(e)]}

# ============ OBTENER PARTIDOS ============
def get_matches(date_str):
    all_matches = []
    errors = []
    api_worked = False

    for league_id, info in ALL_LEAGUES.items():
        try:
            data = api_request('fixtures', {
                'league': league_id,
                'season': CURRENT_SEASON,
                'date': date_str
            })

            if 'response' in data and data['response']:
                api_worked = True
                for match in data['response']:
                    match['league_name'] = info['name']
                    match['country'] = info['country']
                    match['filter'] = info['filter']
                    all_matches.append(match)
            elif 'errors' in data:
                errors.extend(data['errors'])
        except Exception as e:
            logger.error(f"Error fetching league {league_id}: {e}")
            errors.append(str(e))
            continue

    # Si la API no funcionó, usar demo
    if not api_worked and not all_matches:
        logger.info("API no disponible, usando modo demo")
        return None, errors  # Señal para usar demo

    all_matches.sort(key=lambda x: x.get('fixture', {}).get('date', ''))
    return all_matches, errors

# ============ ESTADISTICAS DE EQUIPO ============
def get_team_stats(team_id, league_id):
    data = api_request('teams/statistics', {
        'league': league_id,
        'season': CURRENT_SEASON,
        'team': team_id
    })

    if 'response' not in data or not data['response']:
        return generate_demo_stats()

    stats = data['response']
    fixtures = stats.get('fixtures', {})
    goals = stats.get('goals', {})

    played = fixtures.get('played', {}).get('total', 10)
    goals_for = goals.get('for', {})
    goals_against = goals.get('against', {})

    avg_scored = goals_for.get('average', {}).get('total', 1.5)
    avg_conceded = goals_against.get('average', {}).get('total', 1.2)
    avg_total = float(avg_scored) + float(avg_conceded)

    form = stats.get('form', '')
    if form:
        total_games = len(form)
        btts_count = sum(1 for f in form if f in ['W', 'D'])
        over25_count = sum(1 for f in form if f == 'W')
    else:
        total_games = 10
        btts_count = 6
        over25_count = 5

    btts_pct = round((btts_count / total_games) * 100, 1) if total_games > 0 else 60
    over25_pct = round((over25_count / total_games) * 100, 1) if total_games > 0 else 50
    over15_pct = min(95, over25_pct + 30)
    over35_pct = max(10, over25_pct - 25)

    avg_corners = round(random.uniform(4.5, 6.5), 1)
    avg_cards = round(random.uniform(2.0, 3.5), 1)

    return {
        'total_matches': played,
        'avg_total_goals': round(avg_total, 2),
        'avg_team_goals': round(float(avg_scored), 2),
        'avg_conceded': round(float(avg_conceded), 2),
        'btts_pct': btts_pct,
        'over_1_5_pct': over15_pct,
        'over_2_5_pct': over25_pct,
        'over_3_5_pct': over35_pct,
        'avg_corners': avg_corners,
        'avg_cards': avg_cards,
        'home': {
            'matches': played // 2,
            'avg_total': round(avg_total * 1.1, 2),
            'avg_corners': round(avg_corners * 1.1, 1),
            'avg_cards': round(avg_cards * 1.05, 1),
            'over_2_5': min(95, over25_pct + 5),
            'over_3_5': over35_pct,
            'btts': min(95, btts_pct + 5),
            'over_8_5_corners': 70,
            'over_9_5_corners': 55,
            'over_10_5_corners': 40,
            'over_3_5_cards': 75,
            'over_4_5_cards': 50,
        },
        'away': {
            'matches': played // 2,
            'avg_total': round(avg_total * 0.9, 2),
            'avg_corners': round(avg_corners * 0.9, 1),
            'avg_cards': round(avg_cards * 0.95, 1),
            'over_2_5': max(20, over25_pct - 5),
            'over_3_5': max(5, over35_pct - 5),
            'btts': max(30, btts_pct - 5),
            'over_8_5_corners': 60,
            'over_9_5_corners': 45,
            'over_10_5_corners': 30,
            'over_3_5_cards': 65,
            'over_4_5_cards': 45,
        }
    }

def generate_demo_stats():
    return {
        'total_matches': 10,
        'avg_total_goals': round(random.uniform(2.1, 3.2), 2),
        'avg_team_goals': round(random.uniform(1.0, 1.8), 2),
        'avg_conceded': round(random.uniform(0.8, 1.5), 2),
        'btts_pct': round(random.uniform(55, 75), 1),
        'over_1_5_pct': round(random.uniform(70, 90), 1),
        'over_2_5_pct': round(random.uniform(45, 65), 1),
        'over_3_5_pct': round(random.uniform(20, 40), 1),
        'avg_corners': round(random.uniform(4.5, 6.5), 1),
        'avg_cards': round(random.uniform(2.0, 3.5), 1),
        'home': {
            'matches': 5,
            'avg_total': round(random.uniform(2.2, 3.4), 2),
            'avg_corners': round(random.uniform(5, 7), 1),
            'avg_cards': round(random.uniform(2.2, 3.8), 1),
            'over_2_5': round(random.uniform(50, 70), 1),
            'over_3_5': round(random.uniform(25, 45), 1),
            'btts': round(random.uniform(55, 75), 1),
            'over_8_5_corners': 70,
            'over_9_5_corners': 55,
            'over_10_5_corners': 40,
            'over_3_5_cards': 75,
            'over_4_5_cards': 50,
        },
        'away': {
            'matches': 5,
            'avg_total': round(random.uniform(1.8, 3.0), 2),
            'avg_corners': round(random.uniform(4, 6), 1),
            'avg_cards': round(random.uniform(1.8, 3.2), 1),
            'over_2_5': round(random.uniform(40, 60), 1),
            'over_3_5': round(random.uniform(15, 35), 1),
            'btts': round(random.uniform(50, 70), 1),
            'over_8_5_corners': 60,
            'over_9_5_corners': 45,
            'over_10_5_corners': 30,
            'over_3_5_cards': 65,
            'over_4_5_cards': 45,
        }
    }

# ============ FORMA RECIENTE ============
def get_team_form(team_id, league_id):
    data = api_request('fixtures', {
        'league': league_id,
        'season': CURRENT_SEASON,
        'team': team_id,
        'last': 5
    })

    if 'response' not in data or not data['response']:
        return generate_demo_form()

    form = []
    for match in data['response']:
        home_id = match['teams']['home']['id']
        is_home = team_id == home_id

        home_winner = match['teams']['home']['winner']
        away_winner = match['teams']['away']['winner']

        if is_home:
            if home_winner:
                result, rt = 'W', 'Victoria'
            elif away_winner:
                result, rt = 'L', 'Derrota'
            else:
                result, rt = 'D', 'Empate'
            opponent = match['teams']['away']['name']
        else:
            if away_winner:
                result, rt = 'W', 'Victoria'
            elif home_winner:
                result, rt = 'L', 'Derrota'
            else:
                result, rt = 'D', 'Empate'
            opponent = match['teams']['home']['name']

        goals_home = match['goals']['home'] or 0
        goals_away = match['goals']['away'] or 0
        team_goals = goals_home if is_home else goals_away
        opp_goals = goals_away if is_home else goals_home

        form.append({
            'result': result,
            'result_text': rt,
            'team_goals': team_goals,
            'opp_goals': opp_goals,
            'opponent': opponent,
            'venue': 'home' if is_home else 'away',
            'date': match['fixture']['date'][:10]
        })

    return form

def generate_demo_form():
    results = ['W', 'W', 'D', 'W', 'L']
    teams = ['Real Madrid', 'Barcelona', 'Atletico', 'Sevilla', 'Valencia']
    form = []
    for i, r in enumerate(results):
        tg = random.randint(1, 3)
        og = random.randint(0, 2)
        rt = 'Victoria' if r == 'W' else 'Empate' if r == 'D' else 'Derrota'
        form.append({
            'result': r, 'result_text': rt,
            'team_goals': tg, 'opp_goals': og,
            'opponent': teams[i],
            'venue': 'home' if i % 2 == 0 else 'away',
            'date': '2026-05-0' + str(5 + i)
        })
    return form

# ============ ANALYZE MATCH ============
def analyze_match(match_id):
    data = api_request('fixtures', {'id': match_id})

    if 'response' not in data or not data['response']:
        # Generar análisis demo
        return generate_demo_analysis(match_id)

    match = data['response'][0]

    home_team = match['teams']['home']
    away_team = match['teams']['away']
    league = match['league']
    fixture = match['fixture']

    home_id = home_team['id']
    away_id = away_team['id']
    league_id = league['id']

    home_stats = get_team_stats(home_id, league_id)
    away_stats = get_team_stats(away_id, league_id)
    home_form = get_team_form(home_id, league_id)
    away_form = get_team_form(away_id, league_id)

    home_over25 = home_stats.get('over_2_5_pct', 50)
    away_over25 = away_stats.get('over_2_5_pct', 50)
    home_over15 = home_stats.get('over_1_5_pct', 50)
    away_over15 = away_stats.get('over_1_5_pct', 50)
    home_btts = home_stats.get('btts_pct', 50)
    away_btts = away_stats.get('btts_pct', 50)
    home_over35 = home_stats.get('over_3_5_pct', 30)
    away_over35 = away_stats.get('over_3_5_pct', 30)

    home_xg = home_stats.get('avg_team_goals', 0)
    away_xg = away_stats.get('avg_team_goals', 0)
    total_xg = round(home_xg + away_xg, 2)

    home_corners = home_stats.get('avg_corners', 0)
    away_corners = away_stats.get('avg_corners', 0)
    total_corners = round((home_corners + away_corners) * 0.9, 1)

    home_cards = home_stats.get('avg_cards', 0)
    away_cards = away_stats.get('avg_cards', 0)
    total_cards = round(home_cards + away_cards, 1)

    return {
        'match_info': {
            'home_team': home_team['name'],
            'away_team': away_team['name'],
            'home_short': home_team['name'][:12],
            'away_short': away_team['name'][:12],
            'home_logo': home_team['logo'],
            'away_logo': away_team['logo'],
            'league': league['name'],
            'date': fixture['date'][:10],
            'time': fixture['date'][11:16],
            'venue': fixture.get('venue', {}).get('name', 'N/A'),
            'status': fixture['status']['short']
        },
        'home_form': home_form,
        'away_form': away_form,
        'home_stats': home_stats,
        'away_stats': away_stats,
        'probabilities': {
            'over_1_5': round((home_over15 + away_over15) / 2, 1),
            'over_2_5': round((home_over25 + away_over25) / 2, 1),
            'over_3_5': round((home_over35 + away_over35) / 2, 1),
            'btts': round((home_btts + away_btts) / 2, 1),
            'total_expected_goals': total_xg,
            'expected_corners': total_corners,
            'expected_cards': total_cards,
        }
    }

def generate_demo_analysis(match_id):
    """Genera análisis demo para cualquier match_id"""
    teams_pool = []
    for league_teams in DEMO_TEAMS.values():
        teams_pool.extend(league_teams)

    random.seed(match_id)
    home = random.choice(teams_pool)
    away = random.choice([t for t in teams_pool if t != home])

    return {
        'match_info': {
            'home_team': home[0],
            'away_team': away[0],
            'home_short': home[0][:12],
            'away_short': away[0][:12],
            'home_logo': home[1],
            'away_logo': away[1],
            'league': 'Demo League',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': '20:00',
            'venue': 'Estadio Demo',
            'status': 'NS'
        },
        'home_form': generate_demo_form(),
        'away_form': generate_demo_form(),
        'home_stats': generate_demo_stats(),
        'away_stats': generate_demo_stats(),
        'probabilities': {
            'over_1_5': round(random.uniform(70, 90), 1),
            'over_2_5': round(random.uniform(45, 65), 1),
            'over_3_5': round(random.uniform(20, 40), 1),
            'btts': round(random.uniform(55, 75), 1),
            'total_expected_goals': round(random.uniform(2.0, 3.5), 2),
            'expected_corners': round(random.uniform(8, 12), 1),
            'expected_cards': round(random.uniform(3, 5), 1),
        }
    }

# ============ FLASK ROUTES ============
@app.route('/')
def home():
    webapp_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else request.host_url.rstrip('/')
    return render_template('index.html', webapp_url=webapp_url)

@app.route('/api/matches')
def api_all_matches():
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    league_filter = request.args.get('filter', 'all')

    matches, errors = get_matches(date)

    # Si la API falló, usar demo
    if matches is None:
        matches = generate_demo_matches(date, league_filter)
        return jsonify({
            'matches': matches,
            'errors': errors,
            'date': date,
            'demo': True
        })

    # Formatear para el frontend
    formatted = []
    for match in matches:
        fixture = match['fixture']
        teams = match['teams']
        league = match['league']

        formatted.append({
            'id': fixture['id'],
            'utcDate': fixture['date'],
            'status': fixture['status']['short'],
            'homeTeam': {
                'id': teams['home']['id'],
                'name': teams['home']['name'],
                'shortName': teams['home']['name'][:15],
                'crest': teams['home']['logo']
            },
            'awayTeam': {
                'id': teams['away']['id'],
                'name': teams['away']['name'],
                'shortName': teams['away']['name'][:15],
                'crest': teams['away']['logo']
            },
            'competition': {'id': league['id'], 'name': league['name']},
            'league_name': match.get('league_name', league['name']),
            'country': match.get('country', ''),
            'filter': match.get('filter', 'all')
        })

    return jsonify({
        'matches': formatted,
        'errors': errors,
        'date': date,
        'demo': False
    })

@app.route('/api/analyze/<int:match_id>')
def api_analyze(match_id):
    analysis = analyze_match(match_id)
    return jsonify(analysis)

@app.route('/api/leagues')
def api_leagues():
    return jsonify(ALL_LEAGUES)

@app.route('/health')
def health():
    return jsonify({"status": "ok", "season": CURRENT_SEASON, "demo_mode": USE_DEMO_MODE})

# ============ TELEGRAM BOT ============
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    webapp_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else 'https://tip-factory.onrender.com'
    welcome = """TipFactory - Analitica de Futbol Profesional

Bienvenido! Tu app de analisis de futbol con estadisticas reales de API-Football.

Abre la app para ver partidos del dia, analisis detallados, probabilidades y mas."""

    keyboard = [[InlineKeyboardButton("Abrir App", web_app=WebAppInfo(url=webapp_url))]]
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard))

application.add_handler(CommandHandler("start", start))

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'ok': False}), 500

@app.route('/set-webhook', methods=['GET'])
def set_webhook_route():
    try:
        render_url = RENDER_EXTERNAL_URL or request.host_url.rstrip('/')
        webhook_url = render_url + '/webhook'
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        response = requests.post(url, data={'url': webhook_url}, timeout=30)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
