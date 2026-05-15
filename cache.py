import os
import json
import logging
from datetime import datetime, timedelta, timezone
import redis

logger = logging.getLogger(__name__)

# Conectar a Redis (Render proporciona REDIS_URL automáticamente)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("Redis connected successfully")
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None

# TTLs para diferentes tipos de datos
TTL_FIXTURES = 12 * 3600      # 12 horas
TTL_TEAM_STATS = 24 * 3600    # 24 horas  
TTL_PREDICTIONS = 6 * 3600    # 6 horas
TTL_FORM = 12 * 3600          # 12 horas

def _key(prefix, *parts):
    """Crea una clave de Redis"""
    return f"tipfactory:{prefix}:" + ":".join(str(p) for p in parts)

def cache_get(key):
    """Lee de Redis"""
    if not redis_client:
        return None
    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.error(f"Redis get error: {e}")
    return None

def cache_set(key, data, ttl=3600):
    """Guarda en Redis"""
    if not redis_client:
        return False
    try:
        redis_client.setex(key, ttl, json.dumps(data))
        return True
    except Exception as e:
        logger.error(f"Redis set error: {e}")
    return False

def cache_delete_pattern(pattern):
    """Borra claves por patrón"""
    if not redis_client:
        return
    try:
        for key in redis_client.scan_iter(match=pattern):
            redis_client.delete(key)
    except Exception as e:
        logger.error(f"Redis delete error: {e}")

# ============================================================
# FUNCIONES ESPECÍFICAS PARA TIPFACTORY
# ============================================================

def save_fixtures(date_str, matches, competitions):
    """Guarda fixtures del día en Redis"""
    key = _key("fixtures", date_str)
    data = {
        "matches": matches,
        "competitions": competitions,
        "saved_at": datetime.now(timezone.utc).isoformat()
    }
    return cache_set(key, data, TTL_FIXTURES)

def get_fixtures(date_str):
    """Lee fixtures del día desde Redis"""
    key = _key("fixtures", date_str)
    return cache_get(key)

def save_team_stats(team_id, league_id, season, stats, form_data=None):
    """Guarda stats de equipo en Redis"""
    key = _key("stats", team_id, league_id, season)
    data = {
        "stats": stats,
        "form": form_data,
        "saved_at": datetime.now(timezone.utc).isoformat()
    }
    return cache_set(key, data, TTL_TEAM_STATS)

def get_team_stats(team_id, league_id, season):
    """Lee stats de equipo desde Redis"""
    key = _key("stats", team_id, league_id, season)
    return cache_get(key)

def save_prediction(fixture_id, prediction):
    """Guarda predicción en Redis"""
    key = _key("prediction", fixture_id)
    return cache_set(key, prediction, TTL_PREDICTIONS)

def get_prediction(fixture_id):
    """Lee predicción desde Redis"""
    key = _key("prediction", fixture_id)
    return cache_get(key)

def save_match_stats(fixture_id, stats):
    """Guarda estadísticas de un partido específico"""
    key = _key("match_stats", fixture_id)
    return cache_set(key, stats, TTL_TEAM_STATS)

def get_match_stats(fixture_id):
    """Lee estadísticas de un partido"""
    key = _key("match_stats", fixture_id)
    return cache_get(key)

def save_events(fixture_id, events):
    """Guarda eventos de un partido"""
    key = _key("events", fixture_id)
    return cache_set(key, events, TTL_TEAM_STATS)

def get_events(fixture_id):
    """Lee eventos de un partido"""
    key = _key("events", fixture_id)
    return cache_get(key)

def cleanup_expired():
    """Redis maneja expiración automáticamente, no necesita cleanup manual"""
    pass

def get_cache_stats():
    """Devuelve estadísticas del cache"""
    if not redis_client:
        return {"error": "Redis not connected"}
    try:
        info = redis_client.info()
        return {
            "keys_total": redis_client.dbsize(),
            "memory_used": info.get("used_memory_human", "N/A"),
            "connected": True
        }
    except Exception as e:
        return {"error": str(e)}
