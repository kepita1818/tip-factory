import os
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from scraper import scraper, fallback
from cache import cache

# ============ LOGGING ============
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ FASTAPI APP ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 API iniciada")
    yield
    scraper.close()
    logger.info("👋 API cerrada")

app = FastAPI(
    title="SofaScore Live API",
    description="Datos deportivos en tiempo real con fallback",
    version="2.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ============ HELPERS ============
def format_match(match: dict) -> dict:
    home_team = match.get("homeTeam", {})
    away_team = match.get("awayTeam", {})
    tournament = match.get("tournament", {})
    status = match.get("status", {})
    
    home_score = match.get("homeScore", {})
    away_score = match.get("awayScore", {})
    
    start_ts = match.get("startTimestamp", 0)
    if isinstance(start_ts, str):
        start_ts = int(start_ts)
    
    return {
        "id": match.get("id"),
        "utcDate": datetime.fromtimestamp(start_ts).isoformat() if start_ts else datetime.now().isoformat(),
        "status": status.get("type", "NS"),
        "statusText": status.get("description", "No iniciado"),
        "homeTeam": {
            "id": home_team.get("id"),
            "name": home_team.get("name", "Local"),
            "shortName": home_team.get("shortName", home_team.get("name", "Local")[:15]),
            "crest": home_team.get("crest") or f"https://api.sofascore.app/api/v1/team/{home_team.get('id')}/image"
        },
        "awayTeam": {
            "id": away_team.get("id"),
            "name": away_team.get("name", "Visitante"),
            "shortName": away_team.get("shortName", away_team.get("name", "Visitante")[:15]),
            "crest": away_team.get("crest") or f"https://api.sofascore.app/api/v1/team/{away_team.get('id')}/image"
        },
        "competition": {
            "id": tournament.get("id"),
            "name": tournament.get("name", "Liga")
        },
        "league_name": tournament.get("name", "Liga"),
        "country": tournament.get("category", {}).get("name", "") if isinstance(tournament.get("category"), dict) else match.get("country", ""),
        "homeScore": home_score.get("current") if isinstance(home_score, dict) else home_score,
        "awayScore": away_score.get("current") if isinstance(away_score, dict) else away_score,
        "minute": status.get("minute", 0) if status.get("type") == "inprogress" else None
    }

def extract_stats_from_sofascore(stats_data: list) -> dict:
    result = {
        "avg_total_goals": 2.5,
        "avg_team_goals": 1.3,
        "avg_conceded": 1.2,
        "btts_pct": 55,
        "over_1_5_pct": 70,
        "over_2_5_pct": 50,
        "over_3_5_pct": 30,
        "avg_corners": 5.0,
        "avg_cards": 2.5,
        "home": {},
        "away": {}
    }
    
    if not stats_data or not isinstance(stats_data, list):
        return result
    
    for period in stats_data:
        groups = period.get("groups", [])
        for group in groups:
            stats_items = group.get("statisticsItems", [])
            for item in stats_items:
                name = item.get("name", "").lower()
                home_val = item.get("homeValue", 0)
                away_val = item.get("awayValue", 0)
                
                if "goals" in name or "expected goals" in name:
                    result["avg_team_goals"] = float(home_val) if home_val else result["avg_team_goals"]
                    result["avg_conceded"] = float(away_val) if away_val else result["avg_conceded"]
                
                if "corner" in name:
                    result["avg_corners"] = float(home_val) if home_val else result["avg_corners"]
                
                if "card" in name or "yellow" in name or "red" in name:
                    result["avg_cards"] = float(home_val) if home_val else result["avg_cards"]
    
    result["avg_total_goals"] = round(result["avg_team_goals"] + result["avg_conceded"], 2)
    result["over_1_5_pct"] = min(95, int(result["avg_total_goals"] * 25 + 20))
    result["over_2_5_pct"] = min(90, int(result["avg_total_goals"] * 20 + 10))
    result["over_3_5_pct"] = max(10, int(result["avg_total_goals"] * 12))
    result["btts_pct"] = min(90, int(result["avg_team_goals"] * 15 + result["avg_conceded"] * 15))
    
    result["home"] = {
        "matches": 10,
        "avg_total": round(result["avg_total_goals"] * 1.1, 2),
        "avg_corners": round(result["avg_corners"] * 1.1, 1),
        "avg_cards": round(result["avg_cards"] * 1.05, 1),
        "over_2_5": min(95, result["over_2_5_pct"] + 5),
        "over_3_5": result["over_3_5_pct"],
        "btts": min(95, result["btts_pct"] + 5),
        "over_8_5_corners": 70,
        "over_9_5_corners": 55,
        "over_10_5_corners": 40,
        "over_3_5_cards": 75,
        "over_4_5_cards": 50,
    }
    
    result["away"] = {
        "matches": 10,
        "avg_total": round(result["avg_total_goals"] * 0.9, 2),
        "avg_corners": round(result["avg_corners"] * 0.9, 1),
        "avg_cards": round(result["avg_cards"] * 0.95, 1),
        "over_2_5": max(20, result["over_2_5_pct"] - 5),
        "over_3_5": max(5, result["over_3_5_pct"] - 5),
        "btts": max(30, result["btts_pct"] - 5),
        "over_8_5_corners": 60,
        "over_9_5_corners": 45,
        "over_10_5_corners": 30,
        "over_3_5_cards": 65,
        "over_4_5_cards": 45,
    }
    
    return result

def extract_form_from_h2h(h2h_data: dict, team_id: int, is_home: bool) -> list:
    form = []
    matches = h2h_data.get("teamDuel", {}).get("matches", []) or h2h_data.get("matches", []) or []
    
    for match in matches[:5]:
        home_team = match.get("homeTeam", {})
        away_team = match.get("awayTeam", {})
        home_score = match.get("homeScore", {}).get("current", 0) or 0
        away_score = match.get("awayScore", {}).get("current", 0) or 0
        
        is_team_home = home_team.get("id") == team_id
        team_goals = home_score if is_team_home else away_score
        opp_goals = away_score if is_team_home else home_score
        opponent = away_team.get("name") if is_team_home else home_team.get("name")
        
        if team_goals > opp_goals:
            result, rt = "W", "Victoria"
        elif team_goals < opp_goals:
            result, rt = "L", "Derrota"
        else:
            result, rt = "D", "Empate"
        
        start_ts = match.get("startTimestamp", 0)
        date_str = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d") if start_ts else "2024-01-01"
        
        form.append({
            "result": result,
            "result_text": rt,
            "team_goals": team_goals,
            "opp_goals": opp_goals,
            "opponent": opponent,
            "venue": "home" if is_team_home else "away",
            "date": date_str
        })
    
    return form

def get_demo_matches() -> list:
    """Partidos de demostración cuando todo falla"""
    return [
        {
            "id": 12345678,
            "utcDate": "2026-05-13T20:00:00",
            "status": "NS",
            "statusText": "No iniciado",
            "homeTeam": {
                "id": 2829,
                "name": "Real Madrid",
                "shortName": "Real Madrid",
                "crest": "https://api.sofascore.app/api/v1/team/2829/image"
            },
            "awayTeam": {
                "id": 2817,
                "name": "Barcelona",
                "shortName": "Barcelona",
                "crest": "https://api.sofascore.app/api/v1/team/2817/image"
            },
            "competition": {"id": 8, "name": "La Liga"},
            "league_name": "La Liga",
            "country": "Spain",
            "homeScore": None,
            "awayScore": None,
            "minute": None
        },
        {
            "id": 87654321,
            "utcDate": "2026-05-13T18:30:00",
            "status": "NS",
            "statusText": "No iniciado",
            "homeTeam": {
                "id": 17,
                "name": "Manchester City",
                "shortName": "Man City",
                "crest": "https://api.sofascore.app/api/v1/team/17/image"
            },
            "awayTeam": {
                "id": 35,
                "name": "Liverpool",
                "shortName": "Liverpool",
                "crest": "https://api.sofascore.app/api/v1/team/35/image"
            },
            "competition": {"id": 17, "name": "Premier League"},
            "league_name": "Premier League",
            "country": "England",
            "homeScore": None,
            "awayScore": None,
            "minute": None
        },
        {
            "id": 11111111,
            "utcDate": "2026-05-13T21:00:00",
            "status": "1H",
            "statusText": "Primera mitad",
            "homeTeam": {
                "id": 2692,
                "name": "Bayern Munich",
                "shortName": "Bayern",
                "crest": "https://api.sofascore.app/api/v1/team/2692/image"
            },
            "awayTeam": {
                "id": 2673,
                "name": "Borussia Dortmund",
                "shortName": "Dortmund",
                "crest": "https://api.sofascore.app/api/v1/team/2673/image"
            },
            "competition": {"id": 35, "name": "Bundesliga"},
            "league_name": "Bundesliga",
            "country": "Germany",
            "homeScore": 2,
            "awayScore": 1,
            "minute": 34
        }
    ]

# ============ ROUTES ============
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/matches")
def api_matches(date: str = Query(None, description="YYYY-MM-DD"), demo: bool = Query(False)):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Modo demo forzado
    if demo:
        logger.info("Modo demo activado")
        return get_demo_matches()
    
    # Intentar SofaScore primero
    try:
        logger.info(f"Intentando SofaScore para fecha {date}")
        data = scraper.get_scheduled_events(date)
        events = data.get("events", [])
        logger.info(f"SofaScore devolvio {len(events)} eventos")
        if events:
            return [format_match(e) for e in events]
    except Exception as e:
        logger.warning(f"SofaScore fallo: {e}")
    
    # Fallback a API-Football
    try:
        logger.info("Usando fallback API-Football")
        events = fallback.get_matches(date)
        logger.info(f"API-Football devolvio {len(events)} eventos")
        if events:
            return [format_match(e) for e in events]
    except Exception as e:
        logger.error(f"API-Football fallback fallo: {e}")
    
    # Último recurso: datos demo
    logger.warning("Usando datos de demostracion")
    return get_demo_matches()

@app.get("/api/live")
def api_live():
    try:
        data = scraper.get_live_matches()
        events = data.get("events", [])
        if events:
            return [format_match(e) for e in events]
    except Exception as e:
        logger.warning(f"SofaScore live fallo: {e}")
    
    # Fallback: partidos de hoy con status en juego
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        events = fallback.get_matches(today)
        live_events = [e for e in events if e.get("status", {}).get("type") in ["1H", "2H", "HT", "ET", "P"]]
        return [format_match(e) for e in live_events]
    except Exception as e:
        logger.error(f"Fallback live fallo: {e}")
    
    return []

@app.get("/api/analyze/{match_id}")
def api_analyze(match_id: int):
    try:
        # Intentar SofaScore primero
        match_data = None
        try:
            match_data = scraper.get_match_details(match_id)
        except Exception as e:
            logger.warning(f"SofaScore details fallo: {e}")
        
        # Si falla, usar fallback
        if not match_data:
            match_data = fallback.get_match_details(match_id)
        
        match = match_data if isinstance(match_data, dict) else match_data.get("event", {})
        
        if not match:
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        
        home_team = match.get("homeTeam", {})
        away_team = match.get("awayTeam", {})
        tournament = match.get("tournament", {})
        season = match.get("season", {})
        
        home_id = home_team.get("id")
        away_id = away_team.get("id")
        
        # Intentar estadísticas de SofaScore
        stats_data = {}
        h2h_data = {}
        incidents_data = {}
        
        try:
            stats_data = scraper.get_match_statistics(match_id)
        except Exception as e:
            logger.warning(f"Stats no disponibles: {e}")
        
        try:
            h2h_data = scraper.get_match_h2h(match_id)
        except Exception as e:
            logger.warning(f"H2H no disponible: {e}")
        
        try:
            incidents_data = scraper.get_match_incidents(match_id)
        except Exception as e:
            logger.warning(f"Incidents no disponibles: {e}")
        
        # Extraer estadísticas
        home_stats = extract_stats_from_sofascore(stats_data.get("statistics", []) if isinstance(stats_data, dict) else [])
        away_stats = extract_stats_from_sofascore(stats_data.get("statistics", []) if isinstance(stats_data, dict) else [])
        
        # Forma reciente
        home_form = extract_form_from_h2h(h2h_data, home_id, True)
        away_form = extract_form_from_h2h(h2h_data, away_id, False)
        
        if not home_form:
            home_form = [{"result": "W", "result_text": "Victoria", "team_goals": 2, "opp_goals": 1, "opponent": "Rival", "venue": "home", "date": "2024-01-01"}]
        if not away_form:
            away_form = [{"result": "D", "result_text": "Empate", "team_goals": 1, "opp_goals": 1, "opponent": "Rival", "venue": "away", "date": "2024-01-01"}]
        
        # Calcular probabilidades
        home_over25 = home_stats.get("over_2_5_pct", 50)
        away_over25 = away_stats.get("over_2_5_pct", 50)
        home_over15 = home_stats.get("over_1_5_pct", 50)
        away_over15 = away_stats.get("over_1_5_pct", 50)
        home_btts = home_stats.get("btts_pct", 50)
        away_btts = away_stats.get("btts_pct", 50)
        home_over35 = home_stats.get("over_3_5_pct", 30)
        away_over35 = away_stats.get("over_3_5_pct", 30)
        
        home_xg = home_stats.get("avg_team_goals", 0)
        away_xg = away_stats.get("avg_team_goals", 0)
        total_xg = round(home_xg + away_xg, 2)
        
        home_corners = home_stats.get("avg_corners", 0)
        away_corners = away_stats.get("avg_corners", 0)
        total_corners = round((home_corners + away_corners) * 0.9, 1)
        
        home_cards = home_stats.get("avg_cards", 0)
        away_cards = away_stats.get("avg_cards", 0)
        total_cards = round(home_cards + away_cards, 1)
        
        # Incidentes en vivo
        live_incidents = []
        if incidents_data and isinstance(incidents_data, dict):
            for inc in incidents_data.get("incidents", [])[:10]:
                live_incidents.append({
                    "minute": inc.get("time", 0),
                    "type": inc.get("incidentType", ""),
                    "text": inc.get("text", ""),
                    "player": inc.get("player", {}).get("name", "") if inc.get("player") else ""
                })
        
        start_ts = match.get("startTimestamp", 0)
        if isinstance(start_ts, str):
            start_ts = int(start_ts)
        
        return {
            "match_info": {
                "home_team": home_team.get("name", "Local"),
                "away_team": away_team.get("name", "Visitante"),
                "home_short": home_team.get("shortName", home_team.get("name", "Local"))[:12],
                "away_short": away_team.get("shortName", away_team.get("name", "Visitante"))[:12],
                "home_logo": home_team.get("crest") or f"https://api.sofascore.app/api/v1/team/{home_id}/image",
                "away_logo": away_team.get("crest") or f"https://api.sofascore.app/api/v1/team/{away_id}/image",
                "league": tournament.get("name", "Liga"),
                "date": datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d") if start_ts else datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.fromtimestamp(start_ts).strftime("%H:%M") if start_ts else "20:00",
                "venue": match.get("venue", {}).get("stadium", {}).get("name", "N/A"),
                "status": match.get("status", {}).get("description", "No iniciado"),
                "minute": match.get("status", {}).get("minute", 0),
                "home_score": match.get("homeScore", {}).get("current") if isinstance(match.get("homeScore"), dict) else match.get("homeScore"),
                "away_score": match.get("awayScore", {}).get("current") if isinstance(match.get("awayScore"), dict) else match.get("awayScore")
            },
            "home_form": home_form,
            "away_form": away_form,
            "home_stats": home_stats,
            "away_stats": away_stats,
            "probabilities": {
                "over_1_5": round((home_over15 + away_over15) / 2, 1),
                "over_2_5": round((home_over25 + away_over25) / 2, 1),
                "over_3_5": round((home_over35 + away_over35) / 2, 1),
                "btts": round((home_btts + away_btts) / 2, 1),
                "total_expected_goals": total_xg,
                "expected_corners": total_corners,
                "expected_cards": total_cards,
            },
            "live_incidents": live_incidents,
            "source": "sofascore" if stats_data else "api-football-fallback"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analizando partido {match_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))

@app.get("/api/search")
def api_search(q: str = Query(..., min_length=2)):
    try:
        return scraper.search(q)
    except Exception as e:
        logger.warning(f"SofaScore search fallo: {e}")
        return {"results": []}

@app.get("/api/team/{team_id}")
def api_team(team_id: int):
    try:
        return scraper.get_team_details(team_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/health")
def health():
    return {
        "status": "ok",
        "cache_keys": len(cache._store),
        "timestamp": datetime.now().isoformat(),
        "sofascore_available": True
    }

# ============ MAIN ============
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
