import httpx
import json
from typing import Dict, Any, Optional
from cache import cache


class SofaScoreScraper:
    BASE_URL = "https://www.sofascore.com/api/v1"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.sofascore.com/",
        "Origin": "https://www.sofascore.com",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    def __init__(self):
        self.timeout = httpx.Timeout(15.0, connect=5.0)
        self.client = httpx.Client(
            headers=self.HEADERS,
            timeout=self.timeout,
            follow_redirects=True,
             http2=False
        )

    def _get(self, endpoint: str, cache_key: Optional[str] = None, cache_ttl: int = 60) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        
        if cache_key:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            response = self.client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if cache_key:
                cache.set(cache_key, data, cache_ttl)
            
            return data
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            raise Exception(f"Error de conexion: {str(e)}")

    def get_live_matches(self) -> Dict[str, Any]:
        return self._get("sport/football/events/live", cache_key="live_matches", cache_ttl=30)

    def get_scheduled_events(self, date: str) -> Dict[str, Any]:
        return self._get(
            f"sport/football/scheduled-events/{date}",
            cache_key=f"scheduled_{date}",
            cache_ttl=300
        )

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

    def get_team_statistics(self, team_id: int, tournament_id: int, season_id: int) -> Dict[str, Any]:
        return self._get(
            f"team/{team_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall",
            cache_key=f"team_stats_{team_id}_{tournament_id}_{season_id}",
            cache_ttl=600
        )

    def get_tournament_standings(self, tournament_id: int, season_id: int, type: str = "total") -> Dict[str, Any]:
        return self._get(
            f"unique-tournament/{tournament_id}/season/{season_id}/standings/{type}",
            cache_key=f"standings_{tournament_id}_{season_id}_{type}",
            cache_ttl=600
        )

    def search(self, query: str) -> Dict[str, Any]:
        return self._get(f"search?q={query}", cache_key=f"search_{query}", cache_ttl=300)

    def close(self):
        self.client.close()


scraper = SofaScoreScraper()
