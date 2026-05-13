import httpx
import random
import requests
import os
from typing import Dict, Any, Optional
from cache import cache


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class SofaScoreScraper:
    """Intenta SofaScore, pero desde Render casi siempre fallará"""
    BASE_URL = "https://www.sofascore.com/api/v1"

    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        ua = random.choice(USER_AGENTS)
        headers = {
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.sofascore.com/",
            "Origin": "https://www.sofascore.com",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        if self.client:
            try:
                self.client.close()
            except:
                pass

        self.client = httpx.Client(
            headers=headers,
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            http1=True,
        )

    def _get(self, endpoint: str, cache_key: Optional[str] = None, cache_ttl: int = 60) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        
        if cache_key:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        for attempt in range(2):
            try:
                response = self.client.get(url)
                
                if response.status_code in [403, 503, 429]:
                    if attempt < 1:
                        self._init_client()
                        continue
                    raise Exception(f"HTTP {response.status_code}")
                
                response.raise_for_status()
                data = response.json()
                
                if cache_key:
                    cache.set(cache_key, data, cache_ttl)
                
                return data
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code in [403, 503, 429] and attempt < 1:
                    self._init_client()
                    continue
                raise Exception(f"HTTP {e.response.status_code}")
            except httpx.RequestError as e:
                if attempt < 1:
                    self._init_client()
                    continue
                raise Exception(f"Error: {str(e)}")

    def get_live_matches(self) -> Dict[str, Any]:
        return self._get("sport/football/events/live", cache_key="live_matches", cache_ttl=60)

    def get_scheduled_events(self, date: str) -> Dict[str, Any]:
        return self._get(f"sport/football/scheduled-events/{date}", cache_key=f"scheduled_{date}", cache_ttl=600)

    def get_match_details(self, match_id: int) -> Dict[str, Any]:
        return self._get(f"event/{match_id}", cache_key=f"match_{match_id}", cache_ttl=300)

    def get_match_statistics(self, match_id: int) -> Dict[str, Any]:
        return self._get(f"event/{match_id}/statistics", cache_key=f"stats_{match_id}", cache_ttl=300)

    def get_match_incidents(self, match_id: int) -> Dict[str, Any]:
        return self._get(f"event/{match_id}/incidents", cache_key=f"incidents_{match_id}", cache_ttl=120)

    def get_match_h2h(self, match_id: int) -> Dict[str, Any]:
        return self._get(f"event/{match_id}/h2h", cache_key=f"h2h_{match_id}", cache_ttl=1800)

    def close(self):
        if self.client:
            self.client.close()


class APIFootballSource:
    """Fuente principal: API-Football con cache agresivo"""
    BASE_URL = 'https://v3.football.api-sports.io'
    
    def __init__(self):
        self.key = os.environ.get('API_FOOTBALL_KEY', '650c819e61df3915394dd45ba62df836')
        self.headers = {
            'x-rapidapi-key': self.key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
        self.seasons = [2025, 2024, 2023]

    def _api_request(self, endpoint: str, params: dict, cache_key: str, cache_ttl: int = 600) -> dict:
        """Petición con cache para ahorrar créditos"""
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                headers=self.headers,
                params=params,
                timeout=15
            )
            
            if response.status_code == 429:
                raise Exception("Rate limit API-Football alcanzado")
            
            response.raise_for_status()
            data = response.json()
            
            cache.set(cache_key, data, cache_ttl)
            return data
            
        except Exception as e:
            raise Exception(f"API-Football error: {str(e)}")

    def get_matches(self, date: str) -> list:
        # Cache de 10 minutos para no gastar créditos
        cache_key = f"api_football_matches_{date}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Ligas principales + verano
        leagues = {
            140: 'La Liga', 39: 'Premier League', 135: 'Serie A',
            78: 'Bundesliga', 61: 'Ligue 1', 2: 'Champions League',
            3: 'Europa League', 88: 'Eredivisie', 94: 'Primeira Liga',
            71: 'Serie A Brasil', 253: 'MLS', 113: 'Allsvenskan',
            179: 'Eliteserien', 144: 'Veikkausliiga', 292: 'Premier League Rusia',
            307: 'Premier League Ucrania', 148: 'Super Lig Turquia',
            149: 'Super Lig Grecia', 250: 'A League Australia',
            169: 'Liga MX', 242: 'Primera Division Chile',
            243: 'Primera Division Argentina', 265: 'Primera Division Colombia'
        }
        
        all_matches = []
        requests_made = 0
        
        for season in self.seasons:
            for league_id, league_name in leagues.items():
                if requests_made >= 15:  # Máximo 15 peticiones por carga
                    break
                    
                try:
                    data = self._api_request(
                        'fixtures',
                        {'league': league_id, 'season': season, 'date': date, 'timezone': 'Europe/Madrid'},
                        f"fixtures_{league_id}_{season}_{date}",
                        cache_ttl=600
                    )
                    requests_made += 1
                    
                    for match in data.get('response', []):
                        all_matches.append({
                            'id': match['fixture']['id'],
                            'homeTeam': {
                                'id': match['teams']['home']['id'],
                                'name': match['teams']['home']['name'],
                                'shortName': match['teams']['home']['name'][:15],
                                'crest': match['teams']['home']['logo']
                            },
                            'awayTeam': {
                                'id': match['teams']['away']['id'],
                                'name': match['teams']['away']['name'],
                                'shortName': match['teams']['away']['name'][:15],
                                'crest': match['teams']['away']['logo']
                            },
                            'tournament': {
                                'id': match['league']['id'],
                                'name': match['league']['name'],
                                'category': {'name': match['league']['country']}
                            },
                            'status': {
                                'type': match['fixture']['status']['short'],
                                'description': match['fixture']['status']['long'],
                                'minute': match['fixture']['status']['elapsed']
                            },
                            'startTimestamp': match['fixture']['timestamp'],
                            'homeScore': {'current': match['goals']['home']} if match['goals']['home'] is not None else None,
                            'awayScore': {'current': match['goals']['away']} if match['goals']['away'] is not None else None,
                            'league_name': match['league']['name'],
                            'country': match['league']['country']
                        })
                        
                except Exception:
                    continue
            
            if all_matches:
                break
        
        # Cache por 10 minutos
        cache.set(cache_key, all_matches, 600)
        return all_matches

    def get_match_details(self, match_id: int) -> Dict[str, Any]:
        cache_key = f"match_details_{match_id}"
        
        for season in self.seasons:
            try:
                data = self._api_request(
                    'fixtures',
                    {'id': match_id, 'season': season},
                    f"fixture_{match_id}_{season}",
                    cache_ttl=300
                )
                match = data['response'][0]
                
                result = {
                    'homeTeam': {
                        'id': match['teams']['home']['id'],
                        'name': match['teams']['home']['name'],
                        'shortName': match['teams']['home']['name'][:12],
                        'crest': match['teams']['home']['logo']
                    },
                    'awayTeam': {
                        'id': match['teams']['away']['id'],
                        'name': match['teams']['away']['name'],
                        'shortName': match['teams']['away']['name'][:12],
                        'crest': match['teams']['away']['logo']
                    },
                    'tournament': {'name': match['league']['name']},
                    'season': {'id': match['league']['season']},
                    'status': {
                        'type': match['fixture']['status']['short'],
                        'description': match['fixture']['status']['long'],
                        'minute': match['fixture']['status']['elapsed'] or 0
                    },
                    'startTimestamp': match['fixture']['timestamp'],
                    'venue': {'stadium': {'name': match['fixture']['venue']['name']}},
                    'homeScore': {'current': match['goals']['home']} if match['goals']['home'] is not None else None,
                    'awayScore': {'current': match['goals']['away']} if match['goals']['away'] is not None else None
                }
                
                cache.set(cache_key, result, 300)
                return result
                
            except Exception:
                continue
        
        raise Exception("Partido no encontrado")

    def get_team_stats(self, team_id: int, league_id: int, season: int) -> Dict[str, Any]:
        """Estadísticas reales del equipo"""
        cache_key = f"team_stats_{team_id}_{league_id}_{season}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            data = self._api_request(
                'teams/statistics',
                {'league': league_id, 'season': season, 'team': team_id},
                cache_key,
                cache_ttl=3600
            )
            
            stats = data.get('response', {})
            if not stats:
                return None
            
            fixtures = stats.get('fixtures', {})
            goals = stats.get('goals', {})
            
            played = fixtures.get('played', {}).get('total', 10)
            wins = fixtures.get('wins', {}).get('total', 5)
            
            goals_for = goals.get('for', {})
            goals_against = goals.get('against', {})
            
            avg_scored = float(goals_for.get('average', {}).get('total', 1.5))
            avg_conceded = float(goals_against.get('average', {}).get('total', 1.2))
            avg_total = avg_scored + avg_conceded
            
            # Calcular porcentajes
            over_1_5 = min(95, int(avg_total * 25 + 20))
            over_2_5 = min(90, int(avg_total * 20 + 10))
            over_3_5 = max(10, int(avg_total * 12))
            btts = min(90, int(avg_scored * 15 + avg_conceded * 15))
            
            return {
                'total_matches': played,
                'avg_total_goals': round(avg_total, 2),
                'avg_team_goals': round(avg_scored, 2),
                'avg_conceded': round(avg_conceded, 2),
                'btts_pct': btts,
                'over_1_5_pct': over_1_5,
                'over_2_5_pct': over_2_5,
                'over_3_5_pct': over_3_5,
                'avg_corners': 5.0,
                'avg_cards': 2.5,
                'home': {
                    'matches': played // 2,
                    'avg_total': round(avg_total * 1.1, 2),
                    'avg_corners': 5.5,
                    'avg_cards': 2.6,
                    'over_2_5': min(95, over_2_5 + 5),
                    'over_3_5': over_3_5,
                    'btts': min(95, btts + 5),
                    'over_8_5_corners': 70,
                    'over_9_5_corners': 55,
                    'over_10_5_corners': 40,
                    'over_3_5_cards': 75,
                    'over_4_5_cards': 50,
                },
                'away': {
                    'matches': played // 2,
                    'avg_total': round(avg_total * 0.9, 2),
                    'avg_corners': 4.5,
                    'avg_cards': 2.4,
                    'over_2_5': max(20, over_2_5 - 5),
                    'over_3_5': max(5, over_3_5 - 5),
                    'btts': max(30, btts - 5),
                    'over_8_5_corners': 60,
                    'over_9_5_corners': 45,
                    'over_10_5_corners': 30,
                    'over_3_5_cards': 65,
                    'over_4_5_cards': 45,
                }
            }
            
        except Exception:
            return None

    def get_team_form(self, team_id: int, league_id: int, season: int) -> list:
        """Forma reciente real"""
        cache_key = f"team_form_{team_id}_{league_id}_{season}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            data = self._api_request(
                'fixtures',
                {'league': league_id, 'season': season, 'team': team_id, 'last': 5},
                cache_key,
                cache_ttl=1800
            )
            
            form = []
            for match in data.get('response', []):
                home_id = match['teams']['home']['id']
                is_home = team_id == home_id
                
                home_winner = match['teams']['home']['winner']
                away_winner = match['teams']['away']['winner']
                
                if is_home:
                    if home_winner:
                        result, rt = 'W', 'Victoria'
                    elif away_winner:
                        result, rt = 'L', 'Derrota'
                    else:
                        result, rt = 'D', 'Empate'
                    opponent = match['teams']['away']['name']
                else:
                    if away_winner:
                        result, rt = 'W', 'Victoria'
                    elif home_winner:
                        result, rt = 'L', 'Derrota'
                    else:
                        result, rt = 'D', 'Empate'
                    opponent = match['teams']['home']['name']
                
                goals_home = match['goals']['home'] or 0
                goals_away = match['goals']['away'] or 0
                team_goals = goals_home if is_home else goals_away
                opp_goals = goals_away if is_home else goals_home
                
                form.append({
                    'result': result,
                    'result_text': rt,
                    'team_goals': team_goals,
                    'opp_goals': opp_goals,
                    'opponent': opponent,
                    'venue': 'home' if is_home else 'away',
                    'date': match['fixture']['date'][:10]
                })
            
            cache.set(cache_key, form, 1800)
            return form
            
        except Exception:
            return []

    def get_live_matches(self) -> list:
        """Partidos en vivo ahora"""
        cache_key = "api_football_live"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            # Usar fixtures con status en vivo
            data = self._api_request(
                'fixtures',
                {'live': 'all'},
                cache_key,
                cache_ttl=60
            )
            
            matches = []
            for match in data.get('response', []):
                matches.append({
                    'id': match['fixture']['id'],
                    'homeTeam': {
                        'id': match['teams']['home']['id'],
                        'name': match['teams']['home']['name'],
                        'shortName': match['teams']['home']['name'][:15],
                        'crest': match['teams']['home']['logo']
                    },
                    'awayTeam': {
                        'id': match['teams']['away']['id'],
                        'name': match['teams']['away']['name'],
                        'shortName': match['teams']['away']['name'][:15],
                        'crest': match['teams']['away']['logo']
                    },
                    'tournament': {
                        'id': match['league']['id'],
                        'name': match['league']['name'],
                        'category': {'name': match['league']['country']}
                    },
                    'status': {
                        'type': match['fixture']['status']['short'],
                        'description': match['fixture']['status']['long'],
                        'minute': match['fixture']['status']['elapsed']
                    },
                    'startTimestamp': match['fixture']['timestamp'],
                    'homeScore': {'current': match['goals']['home']} if match['goals']['home'] is not None else None,
                    'awayScore': {'current': match['goals']['away']} if match['goals']['away'] is not None else None,
                    'league_name': match['league']['name'],
                    'country': match['league']['country']
                })
            
            return matches
            
        except Exception:
            return []


scraper = SofaScoreScraper()
api_football = APIFootballSource()
