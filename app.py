import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

# CONFIGURACIÓN MAESTRA: Buscamos archivos en la raíz (.)
app = Flask(__name__, static_folder='.', template_folder='.')

API_KEY = os.environ.get('API_FOOTBALL_KEY', '6c8c1889a9c84616bc3e31ecae00d62f')
API_BASE = 'https://api.football-data.org/v4'
HEADERS = {'X-Auth-Token': API_KEY}

# Mapeo exacto para que el filtro de tu app.js funcione (Spain, England, etc.)
LEAGUE_MAP = {
    'PD': 'Spain', 'PL': 'England', 'SA': 'Italy', 
    'BL1': 'Germany', 'FL1': 'France', 'CL': 'World',
    'DED': 'Netherlands', 'PPL': 'Portugal'
}

# --- RUTAS DE ARCHIVOS (Para que no de 404) ---

@app.route('/')
def index():
    # Intentamos servir el index.html esté donde esté
    for path in ['.', 'templates']:
        if os.path.exists(os.path.join(path, 'index.html')):
            return send_from_directory(path, 'index.html')
    return "Error: No se encuentra index.html en la raiz", 404

@app.route('/static/css/style.css')
def serve_css():
    for path in ['.', 'static/css']:
        if os.path.exists(os.path.join(path, 'style.css')):
            return send_from_directory(path, 'style.css')
    return "", 404

@app.route('/static/js/app.js')
def serve_js():
    for path in ['.', 'static/js']:
        if os.path.exists(os.path.join(path, 'app.js')):
            return send_from_directory(path, 'app.js')
    return "", 404

# --- ENDPOINTS DE DATOS ---

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
            if code in LEAGUE_MAP:
                matches_list.append({
                    'id': m['id'],
                    'utcDate': m['utcDate'],
                    'status': m['status'],
                    'league_name': m['competition']['name'],
                    'country': LEAGUE_MAP[code],
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
    except:
        return jsonify([])

@app.route('/api/analyze/<int:match_id>')
def analyze(match_id):
    try:
        url = f"{API_BASE}/matches/{match_id}"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        return jsonify({
            'match_info': {
                'home_team': res['homeTeam']['name'], 'away_team': res['awayTeam']['name'],
                'home_logo': res['homeTeam']['crest'], 'away_logo': res['awayTeam']['crest'],
                'league': res['competition']['name'], 'date': res['utcDate'][:10]
            },
            'home_stats': {'avg_team_goals': 1.5, 'avg_corners': 5.0, 'avg_cards': 2.0, 'over_2_5_pct': 60, 'btts_pct': 55},
            'away_stats': {'avg_team_goals': 1.1, 'avg_corners': 4.2, 'avg_cards': 2.4, 'over_2_5_pct': 40, 'btts_pct': 50},
            'probabilities': {'over_1_5': 80.0, 'over_2_5': 55.0, 'btts': 52.0, 'expected_corners': 9.2, 'expected_cards': 4.4}
        })
    except:
        return jsonify({'error': 'Error'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
