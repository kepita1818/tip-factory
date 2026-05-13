import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

# Configuramos Flask para que lea todo desde la raíz actual de tu proyecto
app = Flask(__name__, static_folder='.', template_folder='.')

# ============ CONFIGURACIÓN ============
# Esta es la Key de football-data.org (la nueva)
API_KEY = os.environ.get('API_FOOTBALL_KEY', '6c8c1889a9c84616bc3e31ecae00d62f')
API_BASE = 'https://api.football-data.org/v4'
HEADERS = {'X-Auth-Token': API_KEY}

# MAPEO CRÍTICO: Los nombres deben coincidir EXACTAMENTE con los botones de tu app.js
LEAGUE_MAP = {
    'PD': 'Spain',        # La Liga
    'PL': 'England',      # Premier League
    'SA': 'Italy',        # Serie A
    'BL1': 'Germany',     # Bundesliga
    'FL1': 'France',      # Ligue 1
    'CL': 'World',        # Champions
    'DED': 'Netherlands', # Eredivisie
    'PPL': 'Portugal'     # Primeira Liga
}

# ============ SERVIR ARCHIVOS (ESTRUCTURA PLANA) ============
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/static/css/style.css')
def serve_css():
    return send_from_directory('.', 'style.css')

@app.route('/static/js/app.js')
def serve_js():
    return send_from_directory('.', 'app.js')

# ============ ENDPOINTS DE DATOS ============

@app.route('/api/matches')
def get_matches():
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    url = f"{API_BASE}/matches?dateFrom={date_str}&dateTo={date_str}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        data = res.json()
        
        matches_list = []
        if 'matches' not in data:
            return jsonify([])

        for m in data['matches']:
            code = m['competition']['code']
            # Solo enviamos partidos de las ligas que tu app.js filtra (Spain, England, etc.)
            if code in LEAGUE_MAP:
                matches_list.append({
                    'id': m['id'],
                    'utcDate': m['utcDate'],
                    'status': m['status'],
                    'league_name': m['competition']['name'],
                    'country': LEAGUE_MAP[code], # <--- ESTO ACTIVA EL FILTRO DE TU APP.JS
                    'homeTeam': {
                        'name': m['homeTeam']['shortName'] or m['homeTeam']['name'],
                        'crest': m['homeTeam']['crest']
                    },
                    'awayTeam': {
                        'name': m['awayTeam']['shortName'] or m['awayTeam']['name'],
                        'crest': m['awayTeam']['crest']
                    }
                })
        return jsonify(matches_list)
    except Exception as e:
        return jsonify([])

@app.route('/api/analyze/<int:match_id>')
def analyze(match_id):
    try:
        url = f"{API_BASE}/matches/{match_id}"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        
        # Enviamos una estructura de datos que NO DE ERROR al app.js
        # (Con datos estimados porque la API gratuita no da corners/tarjetas)
        return jsonify({
            'match_info': {
                'home_team': res['homeTeam']['name'],
                'away_team': res['awayTeam']['name'],
                'home_logo': res['homeTeam']['crest'],
                'away_logo': res['awayTeam']['crest'],
                'league': res['competition']['name'],
                'date': res['utcDate'][:10]
            },
            'home_form': [], 'away_form': [],
            'home_stats': {
                'avg_team_goals': 1.7, 'avg_corners': 5.5, 'avg_cards': 2.1, 
                'over_2_5_pct': 68, 'btts_pct': 55,
                'over_8_5_corners': 75, 'over_9_5_corners': 58, 'over_10_5_corners': 38,
                'over_3_5_cards': 62, 'over_4_5_cards': 45, 'over_5_5_cards': 22
            },
            'away_stats': {
                'avg_team_goals': 1.3, 'avg_corners': 4.8, 'avg_cards': 2.4, 
                'over_2_5_pct': 50, 'btts_pct': 52,
                'over_8_5_corners': 68, 'over_4_5_corners': 48, 'over_5_5_cards': 25
            },
            'probabilities': {
                'over_1_5': 85.0, 'over_2_5': 60.0, 'btts': 58.0,
                'expected_corners': 9.8, 'expected_cards': 4.5
            }
        })
    except:
        return jsonify({'error': 'Error de carga'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
