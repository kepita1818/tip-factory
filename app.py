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

SUPPORTED_LEAGUES = {
    'La Liga': {'id': 2014, 'country': 'Spain'},
    'Premier League': {'id': 2021, 'country': 'England'},
    'Serie A': {'id': 2019, 'country': 'Italy'},
    'Bundesliga': {'id': 2002, 'country': 'Germany'},
    'Ligue 1': {'id': 2015, 'country': 'France'},
    'Champions League': {'id': 2001, 'country': 'Europe'},
    'Europa League': {'id': 2146, 'country': 'Europe'},
}

# ============ LOGGING ============
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ FLASK APP ============
app = Flask(__name__)

# ============ CACHE ============
cache = {}

def get_cache(key, max_age=3600):
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
        response.raise_for_status()
        data = response.json()
        set_cache(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {}

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
            result = 'W'
        elif team_goals < opp_goals:
            result = 'L'
        else:
            result = 'D'

        form.append({
            'result': result,
            'team_goals': team_goals, 'opp_goals': opp_goals,
            'opponent': match['awayTeam']['name'] if is_home else match['homeTeam']['name'],
            'venue': 'home' if is_home else 'away',
            'date': match['utcDate'][:10]
        })
    return form

def calculate_goal_stats(team_id, competition_id=None):
    date_from = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
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

        team_matches.append({
            'total_goals': total_goals,
            'team_goals': team_goals,
            'btts': home_goals > 0 and away_goals > 0,
            'over_1_5': total_goals > 1.5,
            'over_2_5': total_goals > 2.5,
            'is_home': is_home
        })

    if not team_matches:
        return {}

    total = len(team_matches)
    home_matches = [m for m in team_matches if m['is_home']]
    away_matches = [m for m in team_matches if not m['is_home']]

    return {
        'total_matches': total,
        'avg_total_goals': round(sum(m['total_goals'] for m in team_matches) / total, 2),
        'avg_team_goals': round(sum(m['team_goals'] for m in team_matches) / total, 2),
        'btts_pct': round(sum(1 for m in team_matches if m['btts']) / total * 100, 1),
        'over_1_5_pct': round(sum(1 for m in team_matches if m['over_1_5']) / total * 100, 1),
        'over_2_5_pct': round(sum(1 for m in team_matches if m['over_2_5']) / total * 100, 1),
        'home': {
            'matches': len(home_matches),
            'avg_total': round(sum(m['total_goals'] for m in home_matches) / len(home_matches), 2) if home_matches else 0,
            'over_2_5': round(sum(1 for m in home_matches if m['over_2_5']) / len(home_matches) * 100, 1) if home_matches else 0,
            'btts': round(sum(1 for m in home_matches if m['btts']) / len(home_matches) * 100, 1) if home_matches else 0,
        },
        'away': {
            'matches': len(away_matches),
            'avg_total': round(sum(m['total_goals'] for m in away_matches) / len(away_matches), 2) if away_matches else 0,
            'over_2_5': round(sum(1 for m in away_matches if m['over_2_5']) / len(away_matches) * 100, 1) if away_matches else 0,
            'btts': round(sum(1 for m in away_matches if m['btts']) / len(away_matches) * 100, 1) if away_matches else 0,
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
    home_goal_stats = calculate_goal_stats(home_id, competition_id)
    away_goal_stats = calculate_goal_stats(away_id, competition_id)

    home_over25 = home_goal_stats.get('over_2_5_pct', 50)
    away_over25 = away_goal_stats.get('over_2_5_pct', 50)
    home_btts = home_goal_stats.get('btts_pct', 50)
    away_btts = away_goal_stats.get('btts_pct', 50)

    return {
        'match_info': {
            'home_team': home_team['name'],
            'away_team': away_team['name'],
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
        'home_goal_stats': home_goal_stats,
        'away_goal_stats': away_goal_stats,
        'head_to_head': h2h.get('matches', [])[:5],
        'h2h_aggregates': h2h.get('aggregates'),
        'probabilities': {
            'over_1_5': round((home_goal_stats.get('over_1_5_pct', 50) + away_goal_stats.get('over_1_5_pct', 50)) / 2, 1),
            'over_2_5': round((home_over25 + away_over25) / 2, 1),
            'btts': round((home_btts + away_btts) / 2, 1),
            'total_expected_goals': round(home_goal_stats.get('avg_team_goals', 0) + away_goal_stats.get('avg_team_goals', 0), 2)
        }
    }

# ============ FLASK ROUTES ============
@app.route('/')
def home():
    webapp_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else request.host_url.rstrip('/')
    return render_template('index.html', webapp_url=webapp_url)

@app.route('/api/matches/<int:league_id>')
def api_matches(league_id):
    today = datetime.now().strftime('%Y-%m-%d')
    matches = api_request(f"competitions/{league_id}/matches", {'dateFrom': today, 'dateTo': today})
    return jsonify(matches.get('matches', []))

@app.route('/api/analyze/<int:match_id>')
def api_analyze(match_id):
    analysis = analyze_match(match_id)
    return jsonify(analysis)

@app.route('/api/leagues')
def api_leagues():
    return jsonify(SUPPORTED_LEAGUES)

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

# ============ TELEGRAM BOT ============
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    webapp_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else 'https://tip-factory.onrender.com'
    welcome = """Futbol Analyzer App

Bienvenido! Tu app de analisis de futbol.

Abre la app para ver analisis detallados con estadisticas, probabilidades y mas."""

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
