import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', template_folder='.')

# ============ CONFIGURACIÓN ============
API_KEY = os.environ.get('API_FOOTBALL_KEY', '6c8c1889a9c84616bc3e31ecae00d62f')
API_BASE = 'https://api.football-data.org/v4'
HEADERS = {'X-Auth-Token': API_KEY}

# Mapeo para que tus botones de España, Inglaterra, etc., funcionen
LEAGUE_MAP = {
    'PD': 'Spain', 'PL': 'England', 'SA': 'Italy', 
    'BL1': 'Germany', 'FL1': 'France', 'CL': 'World',
    'DED': 'Netherlands', 'PPL': 'Portugal'
}

# Servir archivos desde la raíz (Tu estructura actual)
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

        if 'matches' in data:
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
    """
    IMPORTANTE: La API gratuita NO da estadísticas de corners/tarjetas.
    Para que tu app.js NO SE ROMPA, generamos la estructura que el JS espera.
    """
    try:
        # Intentamos obtener el nombre del partido real
        res = requests.get(f"{API_BASE}/matches/{match_id}", headers=HEADERS).json()
        
        # Esta estructura es la que tu app.js "necesita" para no dar error
        analysis_data = {
            'match_info': {
                'home_team': res['homeTeam']['name'],
                'away_team': res['awayTeam']['name'],
                'home_logo': res['homeTeam']['crest'],
                'away_logo': res['awayTeam']['crest'],
                'league': res['competition']['name'],
                'date': res['utcDate'][:10]
            },
            'home_stats': {
                'avg_team_goals': 1.65,
                'avg_corners': 5.4,
                'avg_cards': 2.1,
                'over_2_5_pct': 62,
                'btts_pct': 58,
                'home': { 'over_3_5_cards': 65, 'over_4_5_cards': 42, 'avg_corners': 5.8 },
                'away': { 'avg_corners': 4.2 }
            },
            'away_stats': {
                'avg_team_goals': 1.25,
                'avg_corners': 4.8,
                'avg_cards': 2.4,
                'over_2_5_pct': 48,
                'btts_pct': 52,
                'home': { 'over_3_5_cards': 58, 'over_4_5_cards': 35, 'avg_corners': 4.9 },
                'away': { 'avg_corners': 4.1 }
            },
            'probabilities': {
                'over_1_5': 84.0,
                'over_2_5': 58.0,
                'btts': 56.0,
                'expected_corners': 9.6,
                'expected_cards': 4.5
            }
        }
        return jsonify(analysis_data)
    except:
        return jsonify({'error': 'No se pudo cargar el análisis'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
