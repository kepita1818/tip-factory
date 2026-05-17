#!/usr/bin/env python3
"""
Script de precarga diaria para TipFactory.
Se ejecuta 2 veces al día via cron en Render.
Precarga fixtures y stats de equipos en Redis.
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import (
    get_season, get_league_id, get_fixtures_by_date, format_fixture,
    get_team_real_stats, api_get, DEFAULT_COMPETITIONS, COMPETITIONS,
    LEAGUE_IDS, REQUEST_COUNT, RATE_LIMIT, get_fixture_statistics,
    get_fixture_events
)
from cache import (
    save_fixtures, save_team_stats, save_prediction,
    save_match_stats, save_events, get_cache_stats
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MAX_WORKERS = 10

# Ligas más importantes (prioridad para precarga de stats)
TOP_LEAGUES = [
    "PL", "PD", "SA", "BL1", "FL1",      # Top 5 Europa
    "ELC", "SP", "SI", "SD", "FL2",      # Segundas divisiones Europa
    "PPL", "DED", "BE", "CH", "DK", "NO", "FI", "CZ", "GR", "TR",  # Otras Europa
    "CL", "EL", "ECL",                    # Europa
    "BSA", "BRA_B", "ARG", "ARG_B", "COL", "CHI", "URU", "PAR", "ECU", "PER",  # Sudamérica
    "MLS", "MX", "MX_B",                  # Norteamérica
    "JP", "JP_B", "KR", "KR_B", "CN",     # Asia
    "AU_A", "SA_A",                       # Asia/Oceanía
    "EG", "ZA", "MA", "TN"                # África
]

def precache_fixtures():
    """Precarga fixtures para hoy + 2 días"""
    season = get_season()
    today = datetime.now(timezone.utc).date()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
    
    for date_str in dates:
        logger.info(f"Precaching fixtures for {date_str}...")
        all_matches = []
        found_comps = []
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_code = {}
            for code in DEFAULT_COMPETITIONS:
                league_id = get_league_id(code)
                if league_id:
                    future = executor.submit(get_fixtures_by_date, date_str, league_id, season)
                    future_to_code[future] = code
            
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    fixtures = future.result(timeout=30)
                    if fixtures:
                        matches = [format_fixture(f) for f in fixtures]
                        if matches:
                            all_matches.extend(matches)
                            found_comps.append({"code": code, "name": COMPETITIONS.get(code, code)})
                except Exception as e:
                    logger.error(f"Error precaching {code}: {e}")
        
        # Eliminar duplicados
        seen = set()
        unique = []
        for m in all_matches:
            if m["id"] not in seen:
                seen.add(m["id"])
                unique.append(m)
        unique.sort(key=lambda x: x.get("utcDate", ""))
        
        save_fixtures(date_str, unique, found_comps)
        logger.info(f"Saved {len(unique)} fixtures for {date_str}")

def precache_team_stats():
    """Precarga stats para equipos de ligas top"""
    season = get_season()
    
    for code in TOP_LEAGUES:
        league_id = get_league_id(code)
        if not league_id:
            continue
        
        logger.info(f"Precaching team stats for {code}...")
        
        # Obtener fixtures recientes para extraer team_ids
        fixtures_data = api_get(
            "fixtures",
            params={"league": league_id, "season": season, "last": 20, "status": "ft"},
            cache_key=f"precache_teams_{code}_{season}",
            ttl=86400
        )
        
        if not fixtures_data or not isinstance(fixtures_data, dict):
            continue
        
        team_ids = set()
        fixtures_list = fixtures_data.get("response", [])
        
        for f in fixtures_list:
            teams = f.get("teams", {})
            home_id = teams.get("home", {}).get("id")
            away_id = teams.get("away", {}).get("id")
            if home_id: team_ids.add(home_id)
            if away_id: team_ids.add(away_id)
        
        # También precargar stats de partidos individuales
        for f in fixtures_list:
            fixture_id = f.get("fixture", {}).get("id")
            if fixture_id:
                stats = get_fixture_statistics(fixture_id)
                if stats:
                    save_match_stats(fixture_id, stats)
                events = get_fixture_events(fixture_id)
                if events:
                    save_events(fixture_id, events)
        
        # Precargar stats para cada equipo
        for team_id in team_ids:
            try:
                stats = get_team_real_stats(team_id, league_id, season, max_fixtures=10)
                form_data = api_get(
                    "teams/statistics",
                    params={"team": team_id, "league": league_id, "season": season},
                    cache_key=f"team_stats_form_{team_id}_{league_id}_{season}",
                    ttl=86400
                )
                
                save_team_stats(team_id, league_id, season, stats, form_data)
                logger.info(f"Cached team {team_id}")
            except Exception as e:
                logger.error(f"Error precaching team {team_id}: {e}")
        
        logger.info(f"Precached {len(team_ids)} teams for {code}")

def precache_predictions():
    """Precarga predicciones para partidos de hoy en ligas top"""
    from app import get_predictions
    
    season = get_season()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    for code in TOP_LEAGUES[:6]:  # Solo top 6 para no saturar API
        league_id = get_league_id(code)
        if not league_id:
            continue
        
        fixtures = get_fixtures_by_date(today, league_id=league_id, season=season)
        if not fixtures:
            continue
        
        for f in fixtures:
            fixture_id = f.get("fixture", {}).get("id")
            if not fixture_id:
                continue
            
            try:
                pred = get_predictions(fixture_id)
                if pred:
                    save_prediction(fixture_id, pred)
            except Exception as e:
                logger.error(f"Error precaching prediction {fixture_id}: {e}")

def main():
    logger.info("=" * 60)
    logger.info("INICIANDO PRECARGA DIARIA")
    logger.info("=" * 60)
    
    precache_fixtures()
    precache_team_stats()
    precache_predictions()
    
    stats = get_cache_stats()
    logger.info(f"Cache stats: {stats}")
    
    logger.info("=" * 60)
    logger.info(f"PRECARGA COMPLETADA - API requests: {REQUEST_COUNT['total']}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
