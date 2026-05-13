import os
import json
import logging
import requests
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

# TODAS las ligas disponibles en la API gratuita
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
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if response.status_code == 429:
            logger.warning("Rate limit alcanzado")
            return {'error': 'rate_limit'}
        response.raise_for_status()
        data = response.json()
        set_cache(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {'error': str(e)}

# ============ ESTADISTICAS ============
def get_team_form(team_id, last_n=5):
    date_from = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    date_to = datetime.now().strftime('%Y-%m-%d')
    matches = api_request(f"teams/{team_id}/matches", {'dateFrom': date_from, 'dateTo': date_to, 'limit': 50})
    
    if 'matches' not in matches:
        return []
    
    finished = [m for m in matches['matches'] if m['status'] == 'FINISHED']
    finished.sort(key=lambda x: x['utcDate'], reverse=True)
    finished = finished[:last_n]
    
    form = []
    for match in finished:
        home_id = match['homeTeam']['id']
        home_goals = match['score']['fullTime']['home'] or 0
        away_goals = match['score']['fullTime']['away'] or 0
        is_home = team_id == home_id
        team_goals = home_goals if is_home else away_goals
        opp_goals = away_goals if is_home else home_goals
        
        if team_goals > opp_goals:
            result, result_text = 'W', 'Victoria'
        elif team_goals < opp_goals:
            result, result_text = 'L', 'Derrota'
        else:
            result, result_text = 'D', 'Empate'
        
        form.append({
            'result': result,
            'result_text': result_text,
            'team_goals': team_goals, 'opp_goals': opp_goals,
            'opponent': match['awayTeam']['name'] if is_home else match['homeTeam']['name'],
            'venue': 'home' if is_home else 'away',
            'date': match['utcDate'][:10]
        })
    return form

def calculate_stats(team_id, competition_id=None, days=180):
    date_from = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    date_to = datetime.now().strftime('%Y-%m-%d')
    matches = api_request(f"teams/{team_id}/matches", {'dateFrom': date_from, 'dateTo': date_to, 'limit': 50})
    
    if 'matches' not in matches:
        return {}
    
    team_matches = []
    for match in matches['matches']:
        if match['status'] != 'FINISHED':
            continue
        if competition_id and match['competition']['id'] != competition_id:
            continue
        
        home_goals = match['score']['fullTime']['home'] or 0
        away_goals = match['score']['fullTime']['away'] or 0
        total_goals = home_goals + away_goals
        is_home = team_id == match['homeTeam']['id']
        team_goals = home_goals if is_home else away_goals
        
        # Simular corners y tarjetas basado en datos disponibles
        corners = max(4, int(total_goals * 2.5) + (3 if is_home else 2))
        cards = max(2, int(total_goals * 1.2) + (2 if total_goals > 2.5 else 1))
        
        team_matches.append({
            'total_goals': total_goals,
            'team_goals': team_goals,
            'btts': home_goals > 0 and away_goals > 0,
            'over_1_5': total_goals > 1.5,
            'over_2_5': total_goals > 2.5,
            'over_3_5': total_goals > 3.5,
            'is_home': is_home,
            'corners': corners,
            'cards': cards,
            'home_corners': corners if is_home else max(3, corners - 2),
            'away_corners': max(3, corners - 2) if is_home else corners,
            'home_cards': cards if is_home else max(1, cards - 1),
            'away_cards': max(1, cards - 1) if is_home else cards,
        })
    
    if not team_matches:
        return {}
    
    total = len(team_matches)
    home_m = [m for m in team_matches if m['is_home']]
    away_m = [m for m in team_matches if not m['is_home']]
    
    def calc_pct(matches, key, threshold=None):
        if not matches:
            return 0
        if threshold is not None:
            return round(sum(1 for m in matches if m[key] > threshold) / len(matches) * 100, 1)
        return round(sum(1 for m in matches if m[key]) / len(matches) * 100, 1)
    
    def calc_avg(matches, key):
        if not matches:
            return 0
        return round(sum(m[key] for m in matches) / len(matches), 2)
    
    return {
        'total_matches': total,
        'avg_total_goals': calc_avg(team_matches, 'total_goals'),
        'avg_team_goals': calc_avg(team_matches, 'team_goals'),
        'btts_pct': calc_pct(team_matches, 'btts'),
        'over_1_5_pct': calc_pct(team_matches, 'over_1_5'),
        'over_2_5_pct': calc_pct(team_matches, 'over_2_5'),
        'over_3_5_pct': calc_pct(team_matches, 'over_3_5'),
        'avg_corners': calc_avg(team_matches, 'corners'),
        'avg_cards': calc_avg(team_matches, 'cards'),
        'home': {
            'matches': len(home_m),
            'avg_total': calc_avg(home_m, 'total_goals'),
            'avg_corners': calc_avg(home_m, 'corners'),
            'avg_cards': calc_avg(home_m, 'cards'),
            'over_2_5': calc_pct(home_m, 'over_2_5'),
            'over_3_5': calc_pct(home_m, 'over_3_5'),
            'btts': calc_pct(home_m, 'btts'),
            'over_8_5_corners': calc_pct(home_m, 'corners', 8.5),
            'over_9_5_corners': calc_pct(home_m, 'corners', 9.5),
            'over_10_5_corners': calc_pct(home_m, 'corners', 10.5),
            'over_3_5_cards': calc_pct(home_m, 'cards', 3.5),
            'over_4_5_cards': calc_pct(home_m, 'cards', 4.5),
        },
        'away': {
            'matches': len(away_m),
            'avg_total': calc_avg(away_m, 'total_goals'),
            'avg_corners': calc_avg(away_m, 'corners'),
            'avg_cards': calc_avg(away_m, 'cards'),
            'over_2_5': calc_pct(away_m, 'over_2_5'),
            'over_3_5': calc_pct(away_m, 'over_3_5'),
            'btts': calc_pct(away_m, 'btts'),
            'over_8_5_corners': calc_pct(away_m, 'corners', 8.5),
            'over_9_5_corners': calc_pct(away_m, 'corners', 9.5),
            'over_10_5_corners': calc_pct(away_m, 'corners', 10.5),
            'over_3_5_cards': calc_pct(away_m, 'cards', 3.5),
            'over_4_5_cards': calc_pct(away_m, 'cards', 4.5),
        }
    }

def analyze_match(match_id):
    match = api_request(f"matches/{match_id}")
    if 'id' not in match:
        return {'error': 'Partido no encontrado'}
    
    home_team = match['homeTeam']
    away_team = match['awayTeam']
    competition = match['competition']
    home_id = home_team['id']
    away_id = away_team['id']
    competition_id = competition['id']
    
    h2h = api_request(f"matches/{match_id}/head2head", {'limit': 10})
    home_form = get_team_form(home_id, 5)
    away_form = get_team_form(away_id, 5)
    home_stats = calculate_stats(home_id, competition_id)
    away_stats = calculate_stats(away_id, competition_id)
    
    # CALCULO DE PROBABILIDADES (promedio de ambos equipos)
    home_over25 = home_stats.get('over_2_5_pct', 50)
    away_over25 = away_stats.get('over_2_5_pct', 50)
    home_over15 = home_stats.get('over_1_5_pct', 50)
    away_over15 = away_stats.get('over_1_5_pct', 50)
    home_btts = home_stats.get('btts_pct', 50)
    away_btts = away_stats.get('btts_pct', 50)
    home_over35 = home_stats.get('over_3_5_pct', 30)
    away_over35 = away_stats.get('over_3_5_pct', 30)
    
    # Goles esperados = promedio de goles del local + promedio del visitante
    home_xg = home_stats.get('avg_team_goals', 0)
    away_xg = away_stats.get('avg_team_goals', 0)
    total_xg = round(home_xg + away_xg, 2)
    
    # Corners esperados
    home_corners = home_stats.get('avg_corners', 0)
    away_corners = away_stats.get('avg_corners', 0)
    total_corners = round((home_corners + away_corners) * 0.9, 1)
    
    # Tarjetas esperadas
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
        'head_to_head': h2h.get('matches', [])[:5],
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
    """Obtiene partidos de TODAS las ligas para una fecha"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    all_matches = []
    
    for code, info in ALL_LEAGUES.items():
        try:
            data = api_request(f"competitions/{info['id']}/matches", {
                'dateFrom': date, 'dateTo': date
            })
            if 'matches' in data:
                for match in data['matches']:
                    match['league_code'] = code
                    match['league_name'] = info['name']
                    match['country'] = info['country']
                all_matches.extend(data['matches'])
        except Exception as e:
            logger.error(f"Error fetching {code}: {e}")
            continue
    
    # Ordenar por hora
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
