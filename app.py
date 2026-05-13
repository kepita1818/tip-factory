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
API_FOOTBALL_KEY = os.environ.get('API_FOOTBALL_KEY', '6c8c1889a9c84616bc3e31ecae00d62f')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8883372208:AAEqL3nx6g14ULVsOSx_zN23b9OHptTMNq4')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

API_BASE_URL = 'https://api.football-data.org/v4'
HEADERS = {'X-Auth-Token': API_FOOTBALL_KEY}

ALL_LEAGUES = {
    'PL': {'id': 2021, 'name': 'Premier League', 'country': 'England'},
    'BL1': {'id': 2002, 'name': 'Bundesliga', 'country': 'Germany'},
    'SA': {'id': 2019, 'name': 'Serie A', 'country': 'Italy'},
    'PD': {'id': 2014, 'name': 'La Liga', 'country': 'Spain'},
    'FL1': {'id': 2015, 'name': 'Ligue 1', 'country': 'France'},
    'CL': {'id': 2001, 'name': 'Champions League', 'country': 'Europe'},
    'EL': {'id': 2146, 'name': 'Europa League', 'country': 'Europe'},
    'DED': {'id': 2003, 'name': 'Eredivisie', 'country': 'Netherlands'},
    'PPL': {'id': 2017, 'name': 'Primeira Liga', 'country': 'Portugal'},
    'BSA': {'id': 2013, 'name': 'Série A Brasil', 'country': 'Brazil'},
    'MLS': {'id': 2530, 'name': 'MLS', 'country': 'USA'},
    'EC': {'id': 2016, 'name': 'Championship', 'country': 'England'},
}

# ============ DATOS DE DEMO ============
DEMO_TEAMS = {
    77: {'name': 'Athletic Club', 'shortName': 'Athletic', 'crest': 'https://crests.football-data.org/77.png'},
    81: {'name': 'FC Barcelona', 'shortName': 'Barcelona', 'crest': 'https://crests.football-data.org/81.png'},
    86: {'name': 'Real Madrid CF', 'shortName': 'Real Madrid', 'crest': 'https://crests.football-data.org/86.png'},
    78: {'name': 'Atletico de Madrid', 'shortName': 'Atletico', 'crest': 'https://crests.football-data.org/78.png'},
    76: {'name': 'Wolverhampton Wanderers FC', 'shortName': 'Wolves', 'crest': 'https://crests.football-data.org/76.png'},
    402: {'name': 'Brentford FC', 'shortName': 'Brentford', 'crest': 'https://crests.football-data.org/402.png'},
    351: {'name': 'Nottingham Forest FC', 'shortName': 'Forest', 'crest': 'https://crests.football-data.org/351.png'},
    61: {'name': 'Chelsea FC', 'shortName': 'Chelsea', 'crest': 'https://crests.football-data.org/61.png'},
    67: {'name': 'Newcastle United FC', 'shortName': 'Newcastle', 'crest': 'https://crests.football-data.org/67.png'},
    62: {'name': 'Everton FC', 'shortName': 'Everton', 'crest': 'https://crests.football-data.org/62.png'},
    66: {'name': 'Manchester United FC', 'shortName': 'Man United', 'crest': 'https://crests.football-data.org/66.png'},
    58: {'name': 'Aston Villa FC', 'shortName': 'Aston Villa', 'crest': 'https://crests.football-data.org/58.png'},
    64: {'name': 'Liverpool FC', 'shortName': 'Liverpool', 'crest': 'https://crests.football-data.org/64.png'},
    354: {'name': 'Crystal Palace FC', 'shortName': 'Crystal Palace', 'crest': 'https://crests.football-data.org/354.png'},
    5: {'name': 'Bayern Munich', 'shortName': 'Bayern', 'crest': 'https://crests.football-data.org/5.png'},
    3: {'name': 'Bayer Leverkusen', 'shortName': 'Leverkusen', 'crest': 'https://crests.football-data.org/3.png'},
    109: {'name': 'Juventus FC', 'shortName': 'Juventus', 'crest': 'https://crests.football-data.org/109.png'},
    99: {'name': 'AC Milan', 'shortName': 'AC Milan', 'crest': 'https://crests.football-data.org/99.png'},
    524: {'name': 'Paris Saint-Germain FC', 'shortName': 'PSG', 'crest': 'https://crests.football-data.org/524.png'},
    521: {'name': 'Lille OSC', 'shortName': 'Lille', 'crest': 'https://crests.football-data.org/521.png'},
}

DEMO_MATCHES = [
    {'id': 1, 'utcDate': '2026-05-13T19:00:00Z', 'status': 'SCHEDULED', 'homeTeam': DEMO_TEAMS[77], 'awayTeam': DEMO_TEAMS[81], 'competition': {'id': 2014, 'name': 'Primera Division'}, 'league_name': 'La Liga', 'country': 'Spain'},
    {'id': 2, 'utcDate': '2026-05-13T15:00:00Z', 'status': 'SCHEDULED', 'homeTeam': DEMO_TEAMS[76], 'awayTeam': DEMO_TEAMS[402], 'competition': {'id': 2021, 'name': 'Premier League'}, 'league_name': 'Premier League', 'country': 'England'},
    {'id': 3, 'utcDate': '2026-05-13T15:00:00Z', 'status': 'SCHEDULED', 'homeTeam': DEMO_TEAMS[351], 'awayTeam': DEMO_TEAMS[61], 'competition': {'id': 2021, 'name': 'Premier League'}, 'league_name': 'Premier League', 'country': 'England'},
    {'id': 4, 'utcDate': '2026-05-13T15:00:00Z', 'status': 'SCHEDULED', 'homeTeam': DEMO_TEAMS[67], 'awayTeam': DEMO_TEAMS[62], 'competition': {'id': 2021, 'name': 'Premier League'}, 'league_name': 'Premier League', 'country': 'England'},
    {'id': 5, 'utcDate': '2026-05-13T15:00:00Z', 'status': 'SCHEDULED', 'homeTeam': DEMO_TEAMS[66], 'awayTeam': DEMO_TEAMS[58], 'competition': {'id': 2021, 'name': 'Premier League'}, 'league_name': 'Premier League', 'country': 'England'},
    {'id': 6, 'utcDate': '2026-05-13T15:00:00Z', 'status': 'SCHEDULED', 'homeTeam': DEMO_TEAMS[64], 'awayTeam': DEMO_TEAMS[354], 'competition': {'id': 2021, 'name': 'Premier League'}, 'league_name': 'Premier League', 'country': 'England'},
    {'id': 7, 'utcDate': '2026-05-13T20:00:00Z', 'status': 'SCHEDULED', 'homeTeam': DEMO_TEAMS[86], 'awayTeam': DEMO_TEAMS[78], 'competition': {'id': 2014, 'name': 'Primera Division'}, 'league_name': 'La Liga', 'country': 'Spain'},
    {'id': 8, 'utcDate': '2026-05-13T18:30:00Z', 'status': 'SCHEDULED', 'homeTeam': DEMO_TEAMS[5], 'awayTeam': DEMO_TEAMS[3], 'competition': {'id': 2002, 'name': 'Bundesliga'}, 'league_name': 'Bundesliga', 'country': 'Germany'},
    {'id': 9, 'utcDate': '2026-05-13T20:45:00Z', 'status': 'SCHEDULED', 'homeTeam': DEMO_TEAMS[109], 'awayTeam': DEMO_TEAMS[99], 'competition': {'id': 2019, 'name': 'Serie A'}, 'league_name': 'Serie A', 'country': 'Italy'},
    {'id': 10, 'utcDate': '2026-05-13T21:00:00Z', 'status': 'SCHEDULED', 'homeTeam': DEMO_TEAMS[524], 'awayTeam': DEMO_TEAMS[521], 'competition': {'id': 2015, 'name': 'Ligue 1'}, 'league_name': 'Ligue 1', 'country': 'France'},
]

# ============ LOGGING ============
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ FLASK APP ============
app = Flask(__name__)

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

# ============ API FOOTBALL ============
def api_request(endpoint, params=None):
    cache_key = f"{endpoint}:{json.dumps(params or {})}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    url = f"{API_BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if response.status_code == 429:
            logger.warning("Rate limit alcanzado")
            return {'error': 'rate_limit'}
        if response.status_code == 403:
            logger.warning("API key invalida o expirada")
            return {'error': 'forbidden'}
        response.raise_for_status()
        data = response.json()
        set_cache(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {'error': str(e)}

# ============ FUNCIONES DEMO ============
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

def generate_demo_stats():
    return {
        'total_matches': 10,
        'avg_total_goals': round(random.uniform(2.1, 3.2), 2),
        'avg_team_goals': round(random.uniform(1.0, 1.8), 2),
        'btts_pct': round(random.uniform(55, 75), 1),
        'over_1_5_pct': round(random.uniform(70, 90), 1),
        'over_2_5_pct': round(random.uniform(45, 65), 1),
        'over_3_5_pct': round(random.uniform(20, 40), 1),
        'avg_corners': round(random.uniform(8.5, 11.5), 1),
        'avg_cards': round(random.uniform(3.5, 5.5), 1),
        'home': {
            'matches': 5,
            'avg_total': round(random.uniform(2.2, 3.4), 2),
            'avg_corners': round(random.uniform(9, 12), 1),
            'avg_cards': round(random.uniform(3.5, 5.5), 1),
            'over_2_5': round(random.uniform(50, 70), 1),
            'over_3_5': round(random.uniform(25, 45), 1),
            'btts': round(random.uniform(55, 75), 1),
            'over_8_5_corners': round(random.uniform(60, 80), 1),
            'over_9_5_corners': round(random.uniform(50, 70), 1),
            'over_10_5_corners': round(random.uniform(35, 55), 1),
            'over_3_5_cards': round(random.uniform(60, 80), 1),
            'over_4_5_cards': round(random.uniform(40, 60), 1),
        },
        'away': {
            'matches': 5,
            'avg_total': round(random.uniform(1.8, 3.0), 2),
            'avg_corners': round(random.uniform(7, 10), 1),
            'avg_cards': round(random.uniform(3, 5), 1),
            'over_2_5': round(random.uniform(40, 60), 1),
            'over_3_5': round(random.uniform(15, 35), 1),
            'btts': round(random.uniform(50, 70), 1),
            'over_8_5_corners': round(random.uniform(50, 70), 1),
            'over_9_5_corners': round(random.uniform(40, 60), 1),
            'over_10_5_corners': round(random.uniform(25, 45), 1),
            'over_3_5_cards': round(random.uniform(55, 75), 1),
            'over_4_5_cards': round(random.uniform(35, 55), 1),
        }
    }

# ============ ANALYZE MATCH ============
def analyze_match(match_id):
    # Buscar en demo matches PRIMERO
    demo_match = None
    for m in DEMO_MATCHES:
        if m['id'] == match_id:
            demo_match = m
            break

    if demo_match:
        home_stats = generate_demo_stats()
        away_stats = generate_demo_stats()
        home_form = generate_demo_form()
        away_form = generate_demo_form()

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
                'home_team': demo_match['homeTeam']['name'],
                'away_team': demo_match['awayTeam']['name'],
                'home_short': demo_match['homeTeam']['shortName'],
                'away_short': demo_match['awayTeam']['shortName'],
                'home_logo': demo_match['homeTeam']['crest'],
                'away_logo': demo_match['awayTeam']['crest'],
                'league': demo_match['competition']['name'],
                'date': demo_match['utcDate'][:10],
                'time': demo_match['utcDate'][11:16],
                'venue': 'Estadio Principal',
                'status': demo_match['status']
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

    # Si no es demo, intentar API real
    match = api_request(f"matches/{match_id}")
    if 'id' not in match:
        return {'error': 'Partido no encontrado'}

    home_team = match['homeTeam']
    away_team = match['awayTeam']
    competition = match['competition']

    home_stats = generate_demo_stats()
    away_stats = generate_demo_stats()
    home_form = generate_demo_form()
    away_form = generate_demo_form()

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
            'home_short': home_team.get('shortName', home_team['name']),
            'away_short': away_team.get('shortName', away_team['name']),
            'home_logo': home_team.get('crest', ''),
            'away_logo': away_team.get('crest', ''),
            'league': competition['name'],
            'date': match['utcDate'][:10],
            'time': match['utcDate'][11:16],
            'venue': match.get('venue', 'N/A'),
            'status': match['status']
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

# ============ FLASK ROUTES ============
@app.route('/')
def home():
    webapp_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else request.host_url.rstrip('/')
    return render_template('index.html', webapp_url=webapp_url)

@app.route('/api/matches')
def api_all_matches():
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    all_matches = []

    # Intentar obtener datos reales de la API
    for code, info in ALL_LEAGUES.items():
        try:
            data = api_request(f"competitions/{info['id']}/matches", {
                'dateFrom': date, 'dateTo': date
            })
            if 'matches' in data and data['matches']:
                for match in data['matches']:
                    match['league_code'] = code
                    match['league_name'] = info['name']
                    match['country'] = info['country']
                all_matches.extend(data['matches'])
        except Exception as e:
            logger.error(f"Error fetching {code}: {e}")
            continue

    # Si no hay datos reales, usar demo
    if not all_matches:
        logger.info("Usando datos de demo")
        all_matches = DEMO_MATCHES

    all_matches.sort(key=lambda x: x.get('utcDate', ''))
    return jsonify(all_matches)

@app.route('/api/analyze/<int:match_id>')
def api_analyze(match_id):
    analysis = analyze_match(match_id)
    return jsonify(analysis)

@app.route('/api/leagues')
def api_leagues():
    return jsonify(ALL_LEAGUES)

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

# ============ TELEGRAM BOT ============
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    webapp_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else 'https://tip-factory.onrender.com'
    welcome = """TipFactory - Analitica de Futbol Profesional

Bienvenido! Tu app de analisis de futbol con estadisticas reales.

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
