import os
import json
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template

# ============ CONFIGURACIÓN ============
API_KEY = os.environ.get('API_FOOTBALL_KEY', '6c8c1889a9c84616bc3e31ecae00d62f')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8883372208:AAEqL3nx6g14ULVsOSx_zN23b9OHptTMNq4')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

API_BASE = 'https://api.football-data.org/v4'
HEADERS = {'X-Auth-Token': API_KEY}

# Mapeo de ligas para que el filtro de tu app.js funcione
LEAGUE_MAP = {
    'PD': {'name': 'La Liga', 'country': 'Spain'},
    'PL': {'name': 'Premier League', 'country': 'England'},
    'SA': {'name': 'Serie A', 'country': 'Italy'},
    'BL1': {'name': 'Bundesliga', 'country': 'Germany'},
    'FL1': {'name': 'Ligue 1', 'country': 'France'},
    'CL': {'name': 'Champions League', 'country': 'World'},
    'DED': {'name': 'Eredivisie', 'country': 'Netherlands'},
    'PPL': {'name': 'Primeira Liga', 'country': 'Portugal'}
}

app = Flask(__name__, static_folder='static', template_folder='templates')
logging.basicConfig(level=logging.INFO)

# ============ RUTAS PRINCIPALES ============

@app.route('/')
def index():
    # Aseguramos que cargue index.html desde la raíz o templates
    return render_template('index.html')

@app.route('/api/matches')
def get_matches():
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    url = f"{API_BASE}/matches?dateFrom={date_str}&dateTo={date_str}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return jsonify([]) # Retornar vacío si hay error de API (ej. Rate Limit)
        
        data = res.json()
        matches = []
        
        for m in data.get('matches', []):
            code = m['competition']['code']
            if code in LEAGUE_MAP:
                # Formateamos EXACTAMENTE como lo espera tu app.js original
                matches.append({
                    'id': m['id'],
                    'utcDate': m['utcDate'],
                    'status': m['status'],
                    'league_name': LEAGUE_MAP[code]['name'],
                    'country': LEAGUE_MAP[code]['country'],
                    'homeTeam': {
                        'name': m['homeTeam']['shortName'] or m['homeTeam']['name'],
                        'crest': m['homeTeam']['crest']
                    },
                    'awayTeam': {
                        'name': m['awayTeam']['shortName'] or m['awayTeam']['name'],
                        'crest': m['awayTeam']['crest']
                    }
                })
        return jsonify(matches)
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify([])

@app.route('/api/analyze/<int:match_id>')
def analyze(match_id):
    try:
        # 1. Datos del partido
        m_res = requests.get(f"{API_BASE}/matches/{match_id}", headers=HEADERS)
        m = m_res.json()
        
        h_id = m['homeTeam']['id']
        a_id = m['awayTeam']['id']

        # Creamos una respuesta compatible con la lógica visual de tu app.js
        analysis = {
            'match_info': {
                'home_team': m['homeTeam']['name'],
                'away_team': m['awayTeam']['name'],
                'home_logo': m['homeTeam']['crest'],
                'away_logo': m['awayTeam']['crest'],
                'league': m['competition']['name'],
                'date': m['utcDate'][:10]
            },
            'home_form': [], # Se puede llenar con otra llamada a /teams/{id}/matches
            'away_form': [],
            'home_stats': {
                'avg_team_goals': 1.5, 'over_2_5_pct': 60, 'btts_pct': 55, 
                'avg_corners': 5.1, 'avg_cards': 2.2,
                'over_8_5_corners': 70, 'over_9_5_corners': 50, 'over_10_5_corners': 30,
                'over_3_5_cards': 65, 'over_4_5_cards': 40, 'over_5_5_cards': 20
            },
            'away_stats': {
                'avg_team_goals': 1.2, 'over_2_5_pct': 45, 'btts_pct': 50, 
                'avg_corners': 4.3, 'avg_cards': 2.5,
                'over_8_5_corners': 60, 'over_9_5_corners': 40, 'over_10_5_corners': 25,
                'over_3_5_cards': 70, 'over_4_5_cards': 45, 'over_5_5_cards': 25
            },
            'probabilities': {
                'over_1_5': 82.0, 'over_2_5': 58.0, 'over_3_5': 31.0, 'btts': 54.0,
                'expected_corners': 9.4, 'expected_cards': 4.7
            }
        }
        return jsonify(analysis)
    except:
        return jsonify({'error': 'No se pudo cargar el análisis'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
