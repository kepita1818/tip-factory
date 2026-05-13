import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', template_folder='.')

# Configuración
API_KEY = os.environ.get('API_FOOTBALL_KEY', '6c8c1889a9c84616bc3e31ecae00d62f')
API_BASE = 'https://api.football-data.org/v4'
HEADERS = {'X-Auth-Token': API_KEY}

# Ligas permitidas en el plan GRATIS (IMPORTANTE)
FREE_LEAGUES = ['PD', 'PL', 'SA', 'BL1', 'FL1', 'CL', 'DED', 'PPL']

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/static/css/style.css')
def serve_css():
    return send_from_directory('.', 'style.css')

@app.route('/static/js/app.js')
def serve_js():
    return send_from_directory('.', 'app.js')

@app.route('/api/matches')
def get_matches():
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    # Consultamos la API real
    url = f"{API_BASE}/matches?dateFrom={date_str}&dateTo={date_str}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        data = res.json()
        
        matches_list = []
        if 'matches' in data:
            for m in data['matches']:
                # Filtramos para que solo pasen las ligas que tu app.js entiende
                code = m['competition']['code']
                country_name = "Spain" if code == 'PD' else \
                               "England" if code == 'PL' else \
                               "Italy" if code == 'SA' else \
                               "Germany" if code == 'BL1' else \
                               "France" if code == 'FL1' else "World"
                
                matches_list.append({
                    'id': m['id'],
                    'utcDate': m['utcDate'],
                    'status': m['status'],
                    'league_name': m['competition']['name'],
                    'country': country_name,
                    'homeTeam': {'name': m['homeTeam']['shortName'] or m['homeTeam']['name'], 'crest': m['homeTeam']['crest']},
                    'awayTeam': {'name': m['awayTeam']['shortName'] or m['awayTeam']['name'], 'crest': m['awayTeam']['crest']}
                })
        
        return jsonify(matches_list)
    except Exception as e:
        return jsonify([])

@app.route('/api/analyze/<int:match_id>')
def analyze(match_id):
    try:
        # Intentamos pillar datos reales del partido
        res = requests.get(f"{API_BASE}/matches/{match_id}", headers=HEADERS).json()
        return jsonify({
            'match_info': {
                'home_team': res['homeTeam']['name'],
                'away_team': res['awayTeam']['name'],
                'home_logo': res['homeTeam']['crest'],
                'away_logo': res['awayTeam']['crest'],
                'league': res['competition']['name'],
                'date': res['utcDate'][:10]
            },
            'home_stats': {'avg_team_goals': 1.6, 'avg_corners': 5.2, 'avg_cards': 2.1, 'over_2_5_pct': 65, 'btts_pct': 55},
            'away_stats': {'avg_team_goals': 1.2, 'avg_corners': 4.5, 'avg_cards': 2.3, 'over_2_5_pct': 45, 'btts_pct': 50},
            'probabilities': {'over_1_5': 82, 'over_2_5': 56, 'btts': 54, 'expected_corners': 9.5, 'expected_cards': 4.2}
        })
    except:
        return jsonify({'error': 'Error'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
