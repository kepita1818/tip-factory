import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory

# Configuramos Flask para que busque el HTML en la raíz (.)
app = Flask(__name__, template_folder='.')

# ============ CONFIGURACIÓN ============
API_KEY = os.environ.get('API_FOOTBALL_KEY', '6c8c1889a9c84616bc3e31ecae00d62f')
API_BASE = 'https://api.football-data.org/v4'
HEADERS = {'X-Auth-Token': API_KEY}

# Ligas del plan gratuito de football-data.org
LEAGUE_MAP = {
    'PD': 'Spain', 'PL': 'England', 'SA': 'Italy', 
    'BL1': 'Germany', 'FL1': 'France', 'CL': 'World',
    'DED': 'Netherlands', 'PPL': 'Portugal'
}

# ============ EL "TRUCO" PARA TUS CARPETAS ============
# Como tienes los archivos sueltos, estos ruteos engañan al HTML
# para que encuentre el CSS y el JS sin moverlos de sitio.
@app.route('/static/css/style.css')
def serve_css():
    return send_from_directory('.', 'style.css')

@app.route('/static/js/app.js')
def serve_js():
    return send_from_directory('.', 'app.js')

# ============ RUTAS DE LA APP ============

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/matches')
def get_matches():
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    url = f"{API_BASE}/matches?dateFrom={date_str}&dateTo={date_str}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        data = res.json()
        matches = []
        for m in data.get('matches', []):
            code = m['competition']['code']
            if code in LEAGUE_MAP:
                matches.append({
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
        return jsonify(matches)
    except:
        return jsonify([])

@app.route('/api/analyze/<int:match_id>')
def analyze(match_id):
    try:
        res = requests.get(f"{API_BASE}/matches/{match_id}", headers=HEADERS, timeout=10).json()
        # Mandamos datos simulados de corners/tarjetas porque la API free no los da,
        # así evitamos que tu tabla se quede vacía o de error.
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
                'avg_team_goals': 1.6, 'avg_corners': 5.2, 'avg_cards': 2.1, 
                'over_2_5_pct': 65, 'btts_pct': 58,
                'over_8_5_corners': 72, 'over_9_5_corners': 55, 'over_10_5_corners': 35,
                'over_3_5_cards': 60, 'over_4_5_cards': 42, 'over_5_5_cards': 18
            },
            'away_stats': {
                'avg_team_goals': 1.2, 'avg_corners': 4.5, 'avg_cards': 2.3, 
                'over_2_5_pct': 48, 'btts_pct': 52,
                'over_8_5_corners': 65, 'over_4_5_corners': 45, 'over_5_5_cards': 22
            },
            'probabilities': {
                'over_1_5': 84.0, 'over_2_5': 58.0, 'btts': 56.0,
                'expected_corners': 9.7, 'expected_cards': 4.4
            }
        })
    except:
        return jsonify({'error': 'No se pudo cargar'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
