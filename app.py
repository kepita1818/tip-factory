import os
import json
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# ============ CONFIGURACIÓN ============
API_FOOTBALL_KEY = os.environ.get('API_FOOTBALL_KEY', '6c8c1889a9c84616bc3e31ecae00d62f')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8883372208:AAEqL3nx6g14ULVsOSx_zN23b9OHptTMNq4')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

API_BASE_URL = 'https://api.football-data.org/v4'
HEADERS = {'X-Auth-Token': API_FOOTBALL_KEY}

# Ligas disponibles en el plan GRATUITO de football-data.org
FREE_LEAGUES = {
    'PD': 'La Liga', 'PL': 'Premier League', 'SA': 'Serie A',
    'BL1': 'Bundesliga', 'FL1': 'Ligue 1', 'CL': 'Champions League',
    'DED': 'Eredivisie', 'PPL': 'Primeira Liga', 'BSA': 'Serie A Brasil'
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============ SISTEMA DE CACHÉ ============
cache = {}
def get_from_cache(key, expires=600): # 10 minutos
    if key in cache:
        data, ts = cache[key]
        if (datetime.now() - ts).total_seconds() < expires:
            return data
    return None

def save_to_cache(key, data):
    cache[key] = (data, datetime.now())

# ============ HELPER PARA API ============
def call_api(endpoint, params=None):
    cache_key = f"{endpoint}_{json.dumps(params)}"
    cached = get_from_cache(cache_key)
    if cached: return cached

    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=10)
        if response.status_code == 429:
            logger.error("Rate limit excedido (10 req/min).")
            return None
        response.raise_for_status()
        data = response.json()
        save_to_cache(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"Error API: {e}")
        return None

# ============ LOGICA DE PARTIDOS ============
@app.route('/api/matches')
def get_matches():
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    data = call_api('matches', {'dateFrom': date_str, 'dateTo': date_str})
    
    if not data or 'matches' not in data:
        return jsonify([])

    results = []
    for m in data['matches']:
        code = m['competition']['code']
        if code in FREE_LEAGUES:
            results.append({
                'id': m['id'],
                'utcDate': m['utcDate'],
                'status': m['status'],
                'homeTeam': {'name': m['homeTeam']['name'], 'crest': m['homeTeam']['crest']},
                'awayTeam': {'name': m['awayTeam']['name'], 'crest': m['awayTeam']['crest']},
                'league_name': FREE_LEAGUES[code],
                'country': m['area']['name'] if 'area' in m else 'Europe'
            })
    return jsonify(results)

# ============ ANALISIS DETALLADO ============
@app.route('/api/analyze/<int:match_id>')
def analyze_match(match_id):
    match = call_api(f'matches/{match_id}')
    if not match: return jsonify({'error': 'No data'})

    h_id = match['homeTeam']['id']
    a_id = match['awayTeam']['id']

    # Obtenemos ultimos partidos para calcular forma
    h_matches = call_api(f'teams/{h_id}/matches', {'status': 'FINISHED', 'limit': 5})
    a_matches = call_api(f'teams/{a_id}/matches', {'status': 'FINISHED', 'limit': 5})

    def process_form(matches_data, team_id):
        form = []
        scored = 0
        if not matches_data or 'matches' not in matches_data: return [], 0
        for m in matches_data['matches']:
            is_home = m['homeTeam']['id'] == team_id
            goals = m['score']['fullTime']['home' if is_home else 'away']
            opp_goals = m['score']['fullTime']['away' if is_home else 'home']
            res = 'W' if goals > opp_goals else 'D' if goals == opp_goals else 'L'
            form.append({'result': res, 'team_goals': goals, 'opp_goals': opp_goals})
            scored += goals
        return form, round(scored / (len(form) or 1), 2)

    h_form, h_avg = process_form(h_matches, h_id)
    a_form, a_avg = process_form(a_matches, a_id)

    # Nota: football-data.org FREE NO DA corners ni tarjetas. 
    # Mantenemos los campos con valores promedio para no romper el JS.
    return jsonify({
        'match_info': {
            'home_team': match['homeTeam']['name'],
            'away_team': match['awayTeam']['name'],
            'home_logo': match['homeTeam']['crest'],
            'away_logo': match['awayTeam']['crest'],
            'league': match['competition']['name'],
            'date': match['utcDate'][:10]
        },
        'home_form': h_form,
        'away_form': a_form,
        'home_stats': {'avg_team_goals': h_avg, 'over_2_5_pct': 50, 'btts_pct': 50, 'avg_corners': 4.5, 'avg_cards': 2.1},
        'away_stats': {'avg_team_goals': a_avg, 'over_2_5_pct': 45, 'btts_pct': 50, 'avg_corners': 4.2, 'avg_cards': 2.3},
        'probabilities': {
            'over_1_5': 75.0, 'over_2_5': 55.0, 'btts': 52.0,
            'expected_corners': 9.5, 'expected_cards': 4.5
        }
    })

@app.route('/')
def index():
    return render_template('index.html')

# Webhook y Telegram (Simplificado)
@app.route('/webhook', methods=['POST'])
def webhook():
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
