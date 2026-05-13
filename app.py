import os
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from scraper import scraper, api_football
from cache import cache

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 API iniciada")
    yield
    scraper.close()
    logger.info("👋 API cerrada")

app = FastAPI(
    title="Futbol Stats API",
    description="Datos reales via API-Football con cache",
    version="3.0.0",
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
            "crest": home_team.get("crest") or f"https://media.api-sports.io/football/teams/{home_team.get('id')}.png"
        },
        "awayTeam": {
            "id": away_team.get("id"),
            "name": away_team.get("name", "Visitante"),
            "shortName": away_team.get("shortName", away_team.get("name", "Visitante")[:15]),
            "crest": away_team.get("crest") or f"https://media.api-sports.io/football/teams/{away_team.get('id')}.png"
        },
        "competition": {
            "id": tournament.get("id"),
            "name": tournament.get("name", "Liga")
        },
        "league_name": tournament.get("name", "Liga"),
        "country": tournament.get("category", {}).get("name", "") if isinstance(tournament.get("category"), dict) else match.get("country", ""),
        "homeScore": home_score.get("current") if isinstance(home_score, dict) else home_score,
        "awayScore": away_score.get("current") if isinstance(away_score, dict) else away_score,
        "minute": status.get("minute", 0) if status.get("type") in ["1H", "2H", "HT", "ET", "P", "LIVE", "IN_PLAY"] else None
    }

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/matches")
def api_matches(date: str = Query(None, description="YYYY-MM-DD")):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # PRIORIDAD 1: API-Football (datos reales)
    try:
        logger.info(f"API-Football para fecha {date}")
        events = api_football.get_matches(date)
        if events:
            logger.info(f"API-Football: {len(events)} partidos")
            return [format_match(e) for e in events]
    except Exception as e:
        logger.warning(f"API-Football fallo: {e}")
    
    # PRIORIDAD 2: SofaScore (si funciona)
    try:
        data = scraper.get_scheduled_events(date)
        events = data.get("events", [])
        if events:
            logger.info(f"SofaScore: {len(events)} partidos")
            return [format_match(e) for e in events]
    except Exception as e:
        logger.warning(f"SofaScore fallo: {e}")
    
    # FALLBACK: Sin datos
    logger.error("Sin fuentes de datos disponibles")
    return []

@app.get("/api/live")
def api_live():
    # PRIORIDAD 1: API-Football live
    try:
        events = api_football.get_live_matches()
        if events:
            return [format_match(e) for e in events]
    except Exception as e:
        logger.warning(f"API-Football live fallo: {e}")
    
    # PRIORIDAD 2: SofaScore live
    try:
        data = scraper.get_live_matches()
        events = data.get("events", [])
        if events:
            return [format_match(e) for e in events]
    except Exception as e:
        logger.warning(f"SofaScore live fallo: {e}")
    
    return []

@app.get("/api/analyze/{match_id}")
def api_analyze(match_id: int):
    try:
        # Obtener detalles del partido
        match_data = None
        source = "unknown"
        
        try:
            match_data = api_football.get_match_details(match_id)
            source = "api-football"
        except Exception as e:
            logger.warning(f"API-Football details fallo: {e}")
        
        if not match_data:
            try:
                match_data = scraper.get_match_details(match_id)
                source = "sofascore"
            except Exception as e:
                logger.warning(f"SofaScore details fallo: {e}")
        
        if not match_data:
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        
        match = match_data if isinstance(match_data, dict) else match_data.get("event", {})
        
        home_team = match.get("homeTeam", {})
        away_team = match.get("awayTeam", {})
        tournament = match.get("tournament", {})
        season = match.get("season", {})
        
        home_id = home_team.get("id")
        away_id = away_team.get("id")
        league_id = tournament.get("id")
        season_id = season.get("id", 2025)
        
        # Estadísticas reales de API-Football
        home_stats = None
        away_stats = None
        home_form = []
        away_form = []
        
        if source == "api-football" and league_id:
            home_stats = api_football.get_team_stats(home_id, league_id, season_id)
            away_stats = api_football.get_team_stats(away_id, league_id, season_id)
            home_form = api_football.get_team_form(home_id, league_id, season_id)
            away_form = api_football.get_team_form(away_id, league_id, season_id)
        
        # Si no hay stats reales, usar estimaciones
        if not home_stats:
            home_stats = {
                "avg_total_goals": 2.5, "avg_team_goals": 1.3, "avg_conceded": 1.2,
                "btts_pct": 55, "over_1_5_pct": 70, "over_2_5_pct": 50, "over_3_5_pct": 30,
                "avg_corners": 5.0, "avg_cards": 2.5,
                "home": {"matches": 5, "avg_total": 2.8, "avg_corners": 5.5, "avg_cards": 2.6,
                        "over_2_5": 55, "over_3_5": 30, "btts": 60,
                        "over_8_5_corners": 70, "over_9_5_corners": 55, "over_10_5_corners": 40,
                        "over_3_5_cards": 75, "over_4_5_cards": 50}
            }
        
        if not away_stats:
            away_stats = {
                "avg_total_goals": 2.3, "avg_team_goals": 1.1, "avg_conceded": 1.2,
                "btts_pct": 50, "over_1_5_pct": 65, "over_2_5_pct": 45, "over_3_5_pct": 25,
                "avg_corners": 4.5, "avg_cards": 2.3,
                "away": {"matches": 5, "avg_total": 2.1, "avg_corners": 4.0, "avg_cards": 2.1,
                        "over_2_5": 40, "over_3_5": 25, "btts": 50,
                        "over_8_5_corners": 60, "over_9_5_corners": 45, "over_10_5_corners": 30,
                        "over_3_5_cards": 65, "over_4_5_cards": 45}
            }
        
        if not home_form:
            home_form = [{"result": "W", "result_text": "Victoria", "team_goals": 2, "opp_goals": 1, "opponent": "Rival", "venue": "home", "date": "2024-05-01"}]
        if not away_form:
            away_form = [{"result": "D", "result_text": "Empate", "team_goals": 1, "opp_goals": 1, "opponent": "Rival", "venue": "away", "date": "2024-05-01"}]
        
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
        
        start_ts = match.get("startTimestamp", 0)
        if isinstance(start_ts, str):
            start_ts = int(start_ts)
        
        return {
            "match_info": {
                "home_team": home_team.get("name", "Local"),
                "away_team": away_team.get("name", "Visitante"),
                "home_short": home_team.get("shortName", home_team.get("name", "Local"))[:12],
                "away_short": away_team.get("shortName", away_team.get("name", "Visitante"))[:12],
                "home_logo": home_team.get("crest") or f"https://media.api-sports.io/football/teams/{home_id}.png",
                "away_logo": away_team.get("crest") or f"https://media.api-sports.io/football/teams/{away_id}.png",
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
            "source": source
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analizando partido {match_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))

@app.get("/health")
def health():
    return {
        "status": "ok",
        "cache_keys": len(cache._store),
        "timestamp": datetime.now().isoformat(),
        "source": "api-football-primary"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
