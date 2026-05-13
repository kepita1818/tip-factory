import os
import json
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# ============ CONFIGURACION ============
# Nueva API Key y URL
API_FOOTBALL_KEY = os.environ.get('API_FOOTBALL_KEY', '6c8c1889a9c84616bc3e31ecae00d62f')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8883372208:AAEqL3nx6g14ULVsOSx_zN23b9OHptTMNq4')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

API_BASE_URL = 'https://api.football-data.org/v4'
HEADERS = { 'X-Auth-Token': API_FOOTBALL_KEY }

# Ligas soportadas por football-data.org (Free Tier)
# Nota: Los IDs cambian a códigos (PL, PD, etc.)
SUPPORTED_LEAGUES = {
    'PD': {'name': 'La Liga', 'country': 'Spain'},
    'PL': {'name': 'Premier League', 'country': 'England'},
    'SA': {'name': 'Serie A', 'country': 'Italy'},
    'BL1': {'name': 'Bundesliga', 'country': 'Germany'},
    'FL1': {'name': 'Ligue 1', 'country': 'France'},
    'CL': {'name': 'Champions League', 'country': 'World'},
    'DED': {'name': 'Eredivisie', 'country': 'Netherlands'},
    'PPL': {'name': 'Primeira Liga', 'country': 'Portugal'},
    'BSA': {'name': 'Serie A Brasil', 'country': 'Brazil'}
}

# ============ LOGGING ============
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============ CACHE SIMPLE ============
cache = {}
def get_cache(key, max_age=3600): # 1 hora de cache por los límites estrictos de esta API
    if key in cache:
        data, timestamp = cache[key]
        if (datetime.now() - timestamp).seconds < max_age:
            return data
    return None

def set_cache(key, data):
    cache[key] = (data, datetime.now())

# ============ API REQUEST ============
def api_request(endpoint, params=None):
    cache_key = f"{endpoint}:{json.dumps(params or {})}"
    cached = get_cache(cache_key)
    if cached: return cached

    url = f"{API_BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if response.status_code == 429:
            logger.warning("Rate limit alcanzado en football-data.org")
            return None
        response.raise_for_status()
        data = response.json()
        set_cache(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"API Error: {e}")
        return None

# ============ OBTENER PARTIDOS ============
def get_matches(date_str):
    # En football-data.org es mejor pedir todos los partidos del día en una sola llamada
    # debido al límite de 10 peticiones por minuto.
    data = api_request('matches', {'dateFrom': date_str, 'dateTo': date_str})
    
    if not data or 'matches' not in data:
        return []

    formatted_matches = []
    for m in data['matches']:
        league_code = m['competition']['code']
        if league_code in SUPPORTED_LEAGUES:
            formatted_matches.append({
                'id': m['id'],
                'utcDate': m['utcDate'],
                'status': m['status'],
                'homeTeam': {
                    'id': m['homeTeam']['id'],
                    'name': m['homeTeam']['name'],
                    'shortName': m['homeTeam']['shortName'] or m['homeTeam']['name'],
                    'crest': m['homeTeam']['crest']
                },
                'awayTeam': {
                    'id': m['awayTeam']['id'],
                    'name': m['awayTeam']['name'],
                    'shortName': m['awayTeam']['shortName'] or m['awayTeam']['name'],
                    'crest': m['awayTeam']['crest']
                },
                'competition': {'id': m['competition']['id'], 'name': m['competition']['name']},
                'league_name': SUPPORTED_LEAGUES[league_code]['name'],
                'country': SUPPORTED_LEAGUES[league_code]['country']
            })
    return formatted_matches

# ============ ESTADISTICAS Y FORMA ============
def get_team_stats_and_form(team_id):
    """
    Football-data.org no tiene un endpoint de estadísticas tan rico como API-Football.
    Obtenemos los últimos 5 resultados para calcular la forma y promedios.
    """
    data = api_request(f'teams/{team_id}/matches', {'status': 'FINISHED', 'limit': 10})
    
    if not data or 'matches' not in data:
        return None, []

    matches = data['matches']
    form = []
    goals_scored = 0
    goals_conceded = 0
    over25_count = 0
    btts_count = 0

    for m in matches:
        is_home = m['homeTeam']['id'] == team_id
        score = m['score']['fullTime']
        h_goals = score['home'] or 0
        a_goals = score['away'] or 0
        
        t_goals = h_goals if is_home else a_goals
        o_goals = a_goals if is_home else h_goals
        
        # Determinar resultado
        if t_goals > o_goals: res = 'W'
        elif t_goals < o_goals: res = 'L'
        else: res = 'D'
        
        form.append({
            'result': res,
            'result_text': 'Victoria' if res == 'W' else 'Empate' if res == 'D' else 'Derrota',
            'team_goals': t_goals,
            'opp_goals': o_goals,
            'opponent': m['awayTeam']['name'] if is_home else m['homeTeam']['name'],
            'venue': 'home' if is_home else 'away',
            'date': m['utcDate'][:10]
        })
        
        goals_scored += t_goals
        goals_conceded += o_goals
        if (h_goals + a_goals) > 2.5: over25_count += 1
        if h_goals > 0 and a_goals > 0: btts_count += 1

    total = len(matches) if len(matches) > 0 else 1
    stats = {
        'total_matches': total,
        'avg_total_goals': round((goals_scored + goals_conceded) / total, 2),
        'avg_team_goals': round(goals_scored / total, 2),
        'avg_conceded': round(goals_conceded / total, 2),
        'btts_pct': round((btts_count / total) * 100, 1),
        'over_1_5_pct': min(95, round((over25_count + 1) / total * 100, 1)), # Estimación
        'over_2_5_pct': round((over25_count / total) * 100, 1),
        'over_3_5_pct': max(10, round((over25_count - 1) / total * 100, 1)),
        'avg_corners': 5.2, # Valor genérico (la API free no da corners)
        'avg_cards': 2.4,   # Valor genérico (la API free no da tarjetas)
        'home': {'over_8_5_corners': 65, 'over_3_5_cards': 60}, # Placeholders
        'away': {'over_8_5_corners': 55, 'over_3_5_cards': 50}
    }
    
    return stats, form[:5]

# ============ ANALYZE MATCH ============
def analyze_match(match_id):
    match_data = api_request(f'matches/{match_id}')
    if not match_data: return {'error': 'No se pudo obtener info del partido'}

    m = match_data
    home_id = m['homeTeam']['id']
    away_id = m['awayTeam']['id']

    h_stats, h_form = get_team_stats_and_form(home_id)
    a_stats, a_form = get_team_stats_and_form(away_id)

    # Si la API falla, usamos generador para no romper la UI
    if not h_stats: h_stats = {'avg_team_goals': 1.5, 'over_2_5_pct': 50, 'btts_pct': 50}
    if not a_stats: a_stats = {'avg_team_goals': 1.2, 'over_2_5_pct': 45, 'btts_pct': 50}

    return {
        'match_info': {
            'home_team': m['homeTeam']['name'],
            'away_team': m['awayTeam']['name'],
            'home_short': m['homeTeam']['shortName'] or m['homeTeam']['name'],
            'away_short': m['awayTeam']['shortName'] or m['awayTeam']['name'],
            'home_logo': m['homeTeam']['crest'],
            'away_logo': m['awayTeam']['crest'],
            'league': m['competition']['name'],
            'date': m['utcDate'][:10],
            'time': m['utcDate'][11:16],
            'venue': m.get('venue', 'N/A'),
            'status': m['status']
        },
        'home_form': h_form,
        'away_form': a_form,
        'home_stats': h_stats,
        'away_stats': a_stats,
        'probabilities': {
            'over_1_5': round((h_stats.get('over_1_5_pct', 70) + a_stats.get('over_1_5_pct', 70)) / 2, 1),
            'over_2_5': round((h_stats.get('over_2_5_pct', 50) + a_stats.get('over_2_5_pct', 50)) / 2, 1),
            'over_3_5': round((h_stats.get('over_3_5_pct', 25) + a_stats.get('over_3_5_pct', 25)) / 2, 1),
            'btts': round((h_stats.get('btts_pct', 50) + a_stats.get('btts_pct', 50)) / 2, 1),
            'total_expected_goals': round(h_stats.get('avg_team_goals', 0) + a_stats.get('avg_team_goals', 0), 2),
            'expected_corners': 9.5,
            'expected_cards': 4.2
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
    return jsonify(get_matches(date))

@app.route('/api/analyze/<int:match_id>')
def api_analyze(match_id):
    return jsonify(analyze_match(match_id))

@app.route('/health')
def health(): return jsonify({"status": "ok"})

# ============ TELEGRAM BOT ============
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    webapp_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else 'https://tip-factory.onrender.com'
    keyboard = [[InlineKeyboardButton("Abrir App", web_app=WebAppInfo(url=webapp_url))]]
    await update.message.reply_text("TipFactory - Análisis con Football-Data.org", reply_markup=InlineKeyboardMarkup(keyboard))

application.add_handler(CommandHandler("start", start))

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return jsonify({'ok': True})

@app.route('/set-webhook', methods=['GET'])
def set_webhook_route():
    render_url = RENDER_EXTERNAL_URL or request.host_url.rstrip('/')
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    requests.post(url, data={'url': render_url + '/webhook'})
    return jsonify({"status": "webhook set"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
