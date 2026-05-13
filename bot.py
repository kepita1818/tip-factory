"""
Futbol Analyzer Bot - Python version for Render
Webhook-based Telegram bot for football match analysis
"""
import os
import json
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============ CONFIGURACION ============
API_FOOTBALL_KEY = os.environ.get('API_FOOTBALL_KEY', 'TU_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'TU_TOKEN')
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL', '') + '/webhook'

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
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ FLASK APP ============
app = Flask(__name__)

# ============ CACHE SIMPLE ============
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
    matches = api_request(f"teams/{team_id}/matches", {
        'dateFrom': date_from, 'dateTo': date_to, 'limit': 50
    })
    
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
            'result': result, 'result_text': result_text,
            'team_goals': team_goals, 'opp_goals': opp_goals,
            'opponent': match['awayTeam']['name'] if is_home else match['homeTeam']['name'],
            'venue': 'home' if is_home else 'away',
            'date': match['utcDate'][:10]
        })
    return form

def calculate_goal_stats(team_id, competition_id=None):
    date_from = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    date_to = datetime.now().strftime('%Y-%m-%d')
    matches = api_request(f"teams/{team_id}/matches", {
        'dateFrom': date_from, 'dateTo': date_to, 'limit': 50
    })
    
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
            'avg_total': round(sum(m['total_goals'] for m in home_matches) / len(home_matches), 2) if home_matches else 0
        },
        'away': {
            'matches': len(away_matches),
            'avg_total': round(sum(m['total_goals'] for m in away_matches) / len(away_matches), 2) if away_matches else 0
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
            'home_logo': home_team['crest'],
            'away_logo': away_team['crest'],
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

def format_analysis(analysis):
    info = analysis['match_info']
    probs = analysis['probabilities']
    home_form = analysis['home_form']
    away_form = analysis['away_form']
    
    result_emojis = {'W': 'V', 'D': 'E', 'L': 'D'}
    home_form_str = ' '.join(result_emojis.get(f['result'], '?') for f in home_form)
    away_form_str = ' '.join(result_emojis.get(f['result'], '?') for f in away_form)
    
    msg = f"""ANALISIS DEL PARTIDO

{info['home_team']} vs {info['away_team']}
{info['date']} | {info['league']}

------------------------------

FORMA RECIENTE
Local: {home_form_str}
Visitante: {away_form_str}

------------------------------

PROBABILIDADES ESTIMADAS
Over 1.5 Goles: {probs['over_1_5']}%
Over 2.5 Goles: {probs['over_2_5']}%
Ambos Marcan (BTTS): {probs['btts']}%
Goles Esperados Total: {probs['total_expected_goals']}
"""
    
    home_goals = analysis.get('home_goal_stats', {})
    away_goals = analysis.get('away_goal_stats', {})
    if home_goals and away_goals:
        msg += f"""
------------------------------

ESTADISTICAS DE GOLES

Promedio Total:
Local: {home_goals.get('avg_total_goals', 'N/A')}
Visitante: {away_goals.get('avg_total_goals', 'N/A')}

Over 2.5:
Local: {home_goals.get('over_2_5_pct', 'N/A')}%
Visitante: {away_goals.get('over_2_5_pct', 'N/A')}%

BTTS (Ambos Marcan):
Local: {home_goals.get('btts_pct', 'N/A')}%
Visitante: {away_goals.get('btts_pct', 'N/A')}%
"""
    return msg

def format_detailed(analysis):
    info = analysis['match_info']
    msg = f"""DETALLES COMPLETOS

{info['home_team']} vs {info['away_team']}

------------------------------

CORNERS
Datos de corners no disponibles para este partido

------------------------------

TARJETAS
Datos de tarjetas no disponibles para este partido
"""
    
    h2h = analysis.get('head_to_head', [])
    if h2h:
        msg += "\n------------------------------\n\nENFRENTAMIENTOS DIRECTOS (Ultimos 5)\n"
        for match in h2h[:5]:
            home = match['homeTeam']['name']
            away = match['awayTeam']['name']
            home_g = match['score']['fullTime']['home'] or 0
            away_g = match['score']['fullTime']['away'] or 0
            date = match['utcDate'][:10]
            msg += f"{date}: {home} {home_g}-{away_g} {away}\n"
    
    h2h_agg = analysis.get('h2h_aggregates')
    if h2h_agg:
        msg += f"\nRESUMEN H2H:\nTotal partidos: {h2h_agg['numberOfMatches']}\n"
        msg += f"Goles totales: {h2h_agg['totalGoals']}\n"
        if 'homeTeam' in h2h_agg:
            ht = h2h_agg['homeTeam']
            msg += f"{ht['name']}: {ht['wins']}V {ht['draws']}E {ht['losses']}D\n"
    
    msg += "\nNota: Las probabilidades son estimaciones basadas en estadisticas historicas."
    return msg

# ============ TELEGRAM BOT ============
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """Futbol Analyzer Bot

Bienvenido! Soy tu asistente de analisis de futbol.

Que puedo hacer?
- Analizar partidos con estadisticas detalladas
- Ver partidos del dia por liga
- Consultar forma reciente de equipos
- Probabilidades de mercados (Over/Under, BTTS)

Comandos:
/start - Iniciar bot
/analizar - Analizar un partido
/hoy - Partidos de hoy
/ligas - Ligas disponibles
/ayuda - Ayuda completa

Selecciona una opcion:"""
    
    keyboard = [
        [InlineKeyboardButton("Analizar Partido", callback_data='menu:analyze'),
         InlineKeyboardButton("Partidos Hoy", callback_data='menu:today')],
        [InlineKeyboardButton("Ligas", callback_data='menu:leagues'),
         InlineKeyboardButton("Ayuda", callback_data='menu:help')]
    ]
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """Guia de Uso

1. Analizar un Partido:
   - Pulsa Analizar Partido
   - Selecciona la liga
   - Elige el partido

2. Ver Partidos de Hoy:
   - Pulsa Partidos Hoy
   - Selecciona liga

3. Analisis Manual:
   Usa: /analizar EquipoLocal vs EquipoVisitante
   Ejemplo: /analizar Real Madrid vs Barcelona

Ligas soportadas: La Liga, Premier League, Serie A, Bundesliga, Ligue 1, Champions League, Europa League"""
    await update.message.reply_text(help_text)

async def leagues_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for name, info in SUPPORTED_LEAGUES.items():
        keyboard.append([InlineKeyboardButton(name, callback_data=f"league:{info['id']}:{name}")])
    await update.message.reply_text("Selecciona una liga:", reply_markup=InlineKeyboardMarkup(keyboard))

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for name, info in SUPPORTED_LEAGUES.items():
        keyboard.append([InlineKeyboardButton(name, callback_data=f"today:{info['id']}:{name}")])
    today_str = datetime.now().strftime('%Y-%m-%d')
    await update.message.reply_text(f"Partidos del {today_str} - Selecciona liga:", reply_markup=InlineKeyboardMarkup(keyboard))

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = ' '.join(context.args)
    if not args or ' vs ' not in args.lower():
        await update.message.reply_text("Uso: /analizar EquipoLocal vs EquipoVisitante")
        return
    await analyze_text(update, args)

async def analyze_text(update: Update, text: str):
    parts = text.lower().split(' vs ')
    if len(parts) != 2:
        await update.message.reply_text("Formato: Equipo1 vs Equipo2")
        return
    
    home_team, away_team = parts[0].strip(), parts[1].strip()
    await update.message.reply_text(f"Buscando {home_team} vs {away_team}...")
    
    for league_name, league_info in SUPPORTED_LEAGUES.items():
        teams = api_request(f"competitions/{league_info['id']}/teams")
        if 'teams' not in teams:
            continue
        
        home_found = None
        away_found = None
        for team in teams['teams']:
            team_name = team['name'].lower()
            short_name = (team.get('shortName') or '').lower()
            if home_team in team_name or home_team in short_name:
                home_found = team
            if away_team in team_name or away_team in short_name:
                away_found = team
        
        if home_found and away_found:
            today = datetime.now().strftime('%Y-%m-%d')
            matches = api_request(f"competitions/{league_info['id']}/matches", {
                'dateFrom': today, 'dateTo': today
            })
            
            if 'matches' in matches:
                for match in matches['matches']:
                    if (match['homeTeam']['id'] == home_found['id'] and 
                        match['awayTeam']['id'] == away_found['id']):
                        analysis = analyze_match(match['id'])
                        if 'error' not in analysis:
                            await update.message.reply_text(format_analysis(analysis))
                            return
            
            # Buscar en proximos 7 dias
            if not matches.get('matches'):
                date_from = today
                date_to = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
                matches = api_request(f"competitions/{league_info['id']}/matches", {
                    'dateFrom': date_from, 'dateTo': date_to
                })
                if 'matches' in matches:
                    for match in matches['matches']:
                        if (match['homeTeam']['id'] == home_found['id'] and 
                            match['awayTeam']['id'] == away_found['id']):
                            analysis = analyze_match(match['id'])
                            if 'error' not in analysis:
                                await update.message.reply_text(format_analysis(analysis))
                                return
            break
    
    await update.message.reply_text("No encontre el partido. Usa el menu de ligas o verifica los nombres.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith('league:') or data.startswith('today:'):
        parts = data.split(':')
        league_id = int(parts[1])
        league_name = parts[2]
        
        today = datetime.now().strftime('%Y-%m-%d')
        matches = api_request(f"competitions/{league_id}/matches", {
            'dateFrom': today, 'dateTo': today
        })
        
        if 'matches' not in matches or not matches['matches']:
            await query.edit_message_text(f"No hay partidos hoy en {league_name}")
            return
        
        keyboard = []
        for match in matches['matches']:
            home = match['homeTeam']['name']
            away = match['awayTeam']['name']
            time = match['utcDate'][11:16]
            keyboard.append([InlineKeyboardButton(
                f"{home} vs {away} ({time})",
                callback_data=f"match:{match['id']}"
            )])
        
        await query.edit_message_text(
            f"Partidos - {league_name}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('match:'):
        match_id = int(data.split(':')[1])
        await query.edit_message_text("Analizando partido... un momento")
        
        analysis = analyze_match(match_id)
        if 'error' in analysis:
            await query.edit_message_text(f"Error: {analysis['error']}")
            return
        
        keyboard = [
            [InlineKeyboardButton("Mas Detalles", callback_data=f"details:{match_id}")],
            [InlineKeyboardButton("Nuevo Analisis", callback_data="menu:analyze")]
        ]
        await query.edit_message_text(
            format_analysis(analysis),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('details:'):
        match_id = int(data.split(':')[1])
        await query.edit_message_text("Cargando estadisticas detalladas...")
        
        analysis = analyze_match(match_id)
        await query.edit_message_text(format_detailed(analysis))
    
    elif data == 'menu:analyze':
        await leagues_command(update, context)
    elif data == 'menu:today':
        await today_command(update, context)
    elif data == 'menu:leagues':
        await leagues_command(update, context)
    elif data == 'menu:help':
        await help_command(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if ' vs ' in text.lower():
        await analyze_text(update, text)
    else:
        await update.message.reply_text(
            "No entendi. Usa /start para el menu o escribe: Equipo1 vs Equipo2"
        )

# Configurar handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("ayuda", help_command))
application.add_handler(CommandHandler("ligas", leagues_command))
application.add_handler(CommandHandler("hoy", today_command))
application.add_handler(CommandHandler("analizar", analyze_command))
application.add_handler(CallbackQueryHandler(button_callback))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ============ FLASK ROUTES ============
@app.route('/')
def home():
    return jsonify({
        "status": "Futbol Analyzer Bot is running",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/set-webhook', methods=['GET'])
def set_webhook_route():
    try:
        if not WEBHOOK_URL or WEBHOOK_URL == '/webhook':
            return jsonify({'ok': False, 'error': 'WEBHOOK_URL not configured'}), 400
        
        # Usar la URL de Render
        render_url = os.environ.get('RENDER_EXTERNAL_URL', '')
        if render_url:
            webhook_url = render_url + '/webhook'
        else:
            webhook_url = WEBHOOK_URL
        
        # Configurar webhook en Telegram
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        payload = {
            'url': webhook_url,
            'allowed_updates': json.dumps(['message', 'callback_query'])
        }
        response = requests.post(url, data=payload, timeout=30)
        result = response.json()
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Set webhook error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

# ============ MAIN ============
if __name__ == '__main__':
    # Para desarrollo local
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
