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
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class SofaScoreScraper:
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

        for attempt in range(3):
            try:
                response = self.client.get(url)
                
                if response.status_code == 503:
                    if attempt < 2:
                        self._init_client()
                        continue
                    raise Exception("HTTP 503 - SofaScore bloquea esta IP")
                
                response.raise_for_status()
                data = response.json()
                
                if cache_key:
                    cache.set(cache_key, data, cache_ttl)
                
                return data
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503 and attempt < 2:
                    self._init_client()
                    continue
                raise Exception(f"HTTP {e.response.status_code}")
            except httpx.RequestError as e:
                if attempt < 2:
                    self._init_client()
                    continue
                raise Exception(f"Error de conexion: {str(e)}")

    def get_live_matches(self) -> Dict[str, Any]:
        return self._get("sport/football/events/live", cache_key="live_matches", cache_ttl=30)

    def get_scheduled_events(self, date: str) -> Dict[str, Any]:
        return self._get(f"sport/football/scheduled-events/{date}", cache_key=f"scheduled_{date}", cache_ttl=300)

    def get_match_details(self, match_id: int) -> Dict[str, Any]:
        return self._get(f"event/{match_id}", cache_key=f"match_{match_id}", cache_ttl=120)

    def get_match_statistics(self, match_id: int) -> Dict[str, Any]:
        return self._get(f"event/{match_id}/statistics", cache_key=f"stats_{match_id}", cache_ttl=120)

    def get_match_lineups(self, match_id: int) -> Dict[str, Any]:
        return self._get(f"event/{match_id}/lineups", cache_key=f"lineups_{match_id}", cache_ttl=180)

    def get_match_incidents(self, match_id: int) -> Dict[str, Any]:
        return self._get(f"event/{match_id}/incidents", cache_key=f"incidents_{match_id}", cache_ttl=60)

    def get_match_h2h(self, match_id: int) -> Dict[str, Any]:
        return self._get(f"event/{match_id}/h2h", cache_key=f"h2h_{match_id}", cache_ttl=600)

    def get_team_details(self, team_id: int) -> Dict[str, Any]:
        return self._get(f"team/{team_id}", cache_key=f"team_{team_id}", cache_ttl=3600)

    def get_tournament_standings(self, tournament_id: int, season_id: int, type: str = "total") -> Dict[str, Any]:
        return self._get(f"unique-tournament/{tournament_id}/season/{season_id}/standings/{type}", cache_key=f"standings_{tournament_id}_{season_id}_{type}", cache_ttl=600)

    def search(self, query: str) -> Dict[str, Any]:
        return self._get(f"search?q={query}", cache_key=f"search_{query}", cache_ttl=300)

    def close(self):
        if self.client:
            self.client.close()


class APIFootballFallback:
    """Fallback cuando SofaScore falla"""
    BASE_URL = 'https://v3.football.api-sports.io'
    
    def __init__(self):
        self.key = os.environ.get('API_FOOTBALL_KEY', '650c819e61df3915394dd45ba62df836')
        self.headers = {
            'x-rapidapi-key': self.key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }

    def get_matches(self, date: str) -> list:
        leagues = [140, 39, 135, 78, 61, 2, 3, 88, 94, 71, 253]
        all_matches = []
        
        for league_id in leagues:
            try:
                response = requests.get(
                    f"{self.BASE_URL}/fixtures",
                    headers=self.headers,
                    params={'league': league_id, 'season': 2024, 'date': date},
                    timeout=10
                )
                data = response.json()
                
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
                        'status': {'type': match['fixture']['status']['short']},
                        'startTimestamp': int(match['fixture']['timestamp']),
                        'homeScore': {'current': match['goals']['home']} if match['goals']['home'] is not None else None,
                        'awayScore': {'current': match['goals']['away']} if match['goals']['away'] is not None else None,
                        'league_name': match['league']['name'],
                        'country': match['league']['country']
                    })
            except Exception:
                continue
                
        return all_matches

    def get_match_details(self, match_id: int) -> Dict[str, Any]:
        try:
            response = requests.get(
                f"{self.BASE_URL}/fixtures",
                headers=self.headers,
                params={'id': match_id},
                timeout=10
            )
            data = response.json()
            match = data['response'][0]
            
            return {
                'homeTeam': {
                    'id': match['teams']['home']['id'],
                    'name': match['teams']['home']['name'],
                    'shortName': match['teams']['home']['name'][:12]
                },
                'awayTeam': {
                    'id': match['teams']['away']['id'],
                    'name': match['teams']['away']['name'],
                    'shortName': match['teams']['away']['name'][:12]
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
        except Exception as e:
            raise Exception(f"API-Football error: {e}")


scraper = SofaScoreScraper()
fallback = APIFootballFallback()
