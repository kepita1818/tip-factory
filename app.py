import os
import logging
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="TipFactory", version="12.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# === API-FOOTBALL V3 CONFIG ===
API_KEY = "247e8b9eb521d5081463f72ca03ca37b"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

CACHE = {}

# ============================================================
# LIGAS SOPORTADAS - EXPANDIDO MASIVAMENTE
# ============================================================

LEAGUE_IDS = {
    # === TOP 5 EUROPA ===
    "PL": 39, "PD": 140, "SA": 135, "BL1": 78, "FL1": 61,
    
    # === OTRAS EUROPA OCCIDENTAL ===
    "PPL": 94, "DED": 88, "ELC": 40, "SP": 207, "SI": 131,
    "SD": 81, "FL2": 62, "BE": 144, "CH": 207, "AU": 218,
    "DK": 119, "NO": 103, "FI": 244, "CZ": 346, "GR": 197,
    "TR": 203, "UA": 333, "HR": 210, "RO": 283, "SC": 180,
    "RU": 235, "PLN": 106, "IE": 357, "SE": 113, "IS": 164,
    
    # === EUROPA ORIENTAL ===
    "RS": 286, "BG": 172, "HU": 271, "SK": 332, "SI": 131,
    "BA": 290, "MK": 317, "ME": 318, "AL": 319, "MD": 320,
    "EE": 328, "LV": 330, "LT": 331, "BY": 116, "KZ": 325,
    "AM": 342, "GE": 343, "AZ": 324, "UZ": 350, "KG": 351,
    
    # === IBERIA ===
    "CDR": 143, "COPA_ESP": 143, "SUPER_ESP": 556,
    "TACA_POR": 96, "SUPER_POR": 550,
    "COUPE_FR": 66, "TROPHEE": 526,
    "DFB_POKAL": 81, "SUPER_CUP_GER": 529,
    "COPA_ITA": 137, "SUPER_ITA": 547,
    "FA_CUP": 45, "EFL_CUP": 48, "COMM_SHIELD": 528,
    
    # === AMÉRICA DEL SUR ===
    "BSA": 71, "BRA_B": 72, "BRA_C": 75, "BRA_D": 76,
    "CDB": 73, "COPA_BR": 73,
    "ARG": 128, "ARG_B": 129, "ARG_C": 130,
    "COPA_ARG": 130, "SUPER_ARG": 556,
    "COL": 239, "COL_B": 240,
    "CHI": 265, "CHI_B": 266,
    "URU": 268, "URU_B": 269,
    "PAR": 252, "PAR_B": 253,
    "VEN": 277, "VEN_B": 278,
    "BOL": 344, "BOL_B": 345,
    "ECU": 242, "ECU_B": 243,
    "PER": 281, "PER_B": 282,
    
    # === CONMEBOL ===
    "CLI": 13, "CSA": 11, "CSUD": 11, "RECOPA": 24,
    "SUDAMERICANO": 34, "SUDAMERICANO_U20": 35,
    
    # === AMÉRICA DEL NORTE / CENTRO ===
    "MX": 262, "MX_B": 263, "MX_C": 264, "COPA_MX": 265,
    "MLS": 253, "USL": 255, "USL1": 256, "NASL": 257,
    "CAN": 259, "CAN_PL": 259,
    "CRC": 163, "GT": 370, "HN": 300, "SV": 279,
    "PA": 287, "JM": 357, "NI": 358, "CU": 359,
    
    # === CONCACAF ===
    "GOLD": 22, "CCL": 16, "LEAGUES_CUP": 853,
    "NATIONS_CA": 31, "COPA_ORO": 22,
    
    # === ASIA ===
    "JP": 98, "JP_B": 99, "JP_C": 100, "JP_LC": 101,
    "KR": 292, "KR_B": 293, "KR_C": 294,
    "CN": 169, "CN_B": 170, "CN_C": 171,
    "TH": 295, "TH_B": 296,
    "IDN": 274, "MYS": 274, "SGP": 275, "VNM": 276,
    "PH": 297, "MM": 298, "KH": 299, "LA": 301,
    "IR": 291, "IQ": 302, "JO": 303, "LB": 304,
    "SY": 305, "YE": 306,
    "SA_A": 307, "QA": 340, "AE": 301, "KW": 308,
    "BH": 309, "OM": 310,
    "UZ": 350, "KG": 351, "TJ": 352, "TM": 353,
    "IN": 323, "BD": 324, "PK": 325, "LK": 326,
    "NP": 327, "BT": 328, "MV": 329,
    "AU_A": 113, "AU_B": 114, "NZ": 115,
    
    # === AFC ===
    "ACL": 17, "ACL2": 18, "AFC_CUP": 18,
    "ASIA": 7, "ASIA_U23": 23,
    
    # === ÁFRICA ===
    "EG": 233, "EG_B": 234, "EG_C": 235,
    "ZA": 289, "ZA_B": 290,
    "MA": 200, "TN": 194, "DZ": 186,
    "NG": 371, "GH": 376, "CI": 372, "SN": 373,
    "CM": 374, "AO": 375, "MZ": 377, "ZM": 378,
    "ZW": 379, "BW": 380, "NA": 381, "SZ": 382,
    "LS": 383, "ET": 384, "SD": 385, "SS": 386,
    "UG": 387, "KE": 388, "TZ": 389, "RW": 390,
    "BI": 391, "CD": 392, "CG": 393, "GA": 394,
    "GQ": 395, "ST": 396, "TD": 397, "CF": 398,
    "BJ": 399, "TG": 400, "BF": 401, "ML": 402,
    "NE": 403, "MR": 404, "GN": 405, "GW": 406,
    "SL": 407, "LR": 408, "GM": 409, "CV": 410,
    "DJ": 411, "ER": 412, "SO": 413, "MG": 414,
    "KM": 415, "MU": 416, "SC_AFR": 417, "RE": 418,
    
    # === CAF ===
    "AFCON": 6, "AFCON_U23": 29, "AFCON_U20": 30,
    "CAF_CL": 12, "CAF_CC": 14, "CAF_SC": 15,
    
    # === OCEANÍA ===
    "OFC": 32, "OFC_U20": 33,
    "FIJI": 419, "PNG": 420, "SOL": 421, "VAN": 422,
    "NCL": 423, "TAH": 424, "SAM": 425, "TGA": 426,
    
    # === MUNDIALES / INTERNACIONALES ===
    "WC": 1, "EURO": 4, "COPA": 9,
    "NATIONS": 5, "WCC": 10,
    "CONFED": 21, "OLYMPICS": 25, "OLYMPICS_W": 26,
    "U20_WC": 27, "U17_WC": 28,
    
    # === UEFA ===
    "CL": 2, "EL": 3, "ECL": 848,
    "SUPER_CUP_UEFA": 531,
    "YOUTH_LEAGUE": 159,
    "UEFA_NATIONS": 5,
    
    # === AMISTOSOS / OTROS ===
    "FRIENDLY_INT": 10, "FRIENDLY_CLUB": 11,
}

COMPETITIONS = {
    # === TOP 5 ===
    "PL": "Premier League", "PD": "La Liga", "SA": "Serie A",
    "BL1": "Bundesliga", "FL1": "Ligue 1",
    
    # === OTRAS EUROPA ===
    "PPL": "Primeira Liga", "DED": "Eredivisie", "ELC": "Championship",
    "SP": "La Liga 2", "SI": "Serie B", "SD": "2. Bundesliga",
    "FL2": "Ligue 2", "BE": "Jupiler Pro League", "CH": "Super League Suiza",
    "AU": "Bundesliga Austria", "DK": "Superliga Dinamarca",
    "NO": "Eliteserien", "FI": "Veikkausliiga", "CZ": "First League Checa",
    "GR": "Super League Grecia", "TR": "Süper Lig",
    "UA": "Premier League Ucrania", "HR": "HNL Croacia",
    "RO": "Liga I Rumanía", "SC": "Premiership Escocia",
    "RU": "Premier League Rusia", "PLN": "Ekstraklasa Polonia",
    "IE": "Premier Division Irlanda", "SE": "Allsvenskan Suecia",
    "IS": "Besta deild Islandia",
    
    # === EUROPA ORIENTAL ===
    "RS": "SuperLiga Serbia", "BG": "First League Bulgaria",
    "HU": "Nemzeti Bajnokság", "SK": "Fortuna Liga Eslovaquia",
    "BA": "Premier Liga Bosnia", "MK": "First League Macedonia",
    "ME": "First League Montenegro", "AL": "Kategoria Superiore",
    "MD": "Super Liga Moldavia", "EE": "Meistriliiga Estonia",
    "LV": "Virsliga Letonia", "LT": "A Lyga Lituania",
    "BY": "Premier League Bielorrusia", "KZ": "Premier League Kazajistán",
    "AM": "Premier League Armenia", "GE": "Erovnuli Liga Georgia",
    "AZ": "Premier League Azerbaiyán", "UZ": "Super League Uzbekistán",
    "KG": "Premier League Kirguistán",
    
    # === COPAS EUROPA ===
    "CDR": "Copa del Rey", "COPA_ESP": "Copa del Rey",
    "SUPER_ESP": "Supercopa España", "TACA_POR": "Taça de Portugal",
    "SUPER_POR": "Supertaça Portugal", "COUPE_FR": "Coupe de France",
    "TROPHEE": "Trophée des Champions", "DFB_POKAL": "DFB-Pokal",
    "SUPER_CUP_GER": "Supercopa Alemania", "COPA_ITA": "Coppa Italia",
    "SUPER_ITA": "Supercoppa Italiana", "FA_CUP": "FA Cup",
    "EFL_CUP": "EFL Cup", "COMM_SHIELD": "Community Shield",
    
    # === SUDAMÉRICA ===
    "BSA": "Brasileirão", "BRA_B": "Série B Brasil",
    "BRA_C": "Série C Brasil", "BRA_D": "Série D Brasil",
    "CDB": "Copa do Brasil", "COPA_BR": "Copa do Brasil",
    "ARG": "Liga Profesional Argentina", "ARG_B": "Primera Nacional",
    "ARG_C": "Primera C Argentina", "COPA_ARG": "Copa Argentina",
    "SUPER_ARG": "Supercopa Argentina", "COL": "Primera A Colombia",
    "COL_B": "Primera B Colombia", "CHI": "Primera División Chile",
    "CHI_B": "Primera B Chile", "URU": "Primera División Uruguay",
    "URU_B": "Segunda División Uruguay", "PAR": "Primera División Paraguay",
    "PAR_B": "División Intermedia Paraguay", "VEN": "Primera División Venezuela",
    "VEN_B": "Segunda División Venezuela", "BOL": "División Profesional Bolivia",
    "BOL_B": "Nacional B Bolivia", "ECU": "Serie A Ecuador",
    "ECU_B": "Serie B Ecuador", "PER": "Liga 1 Perú",
    "PER_B": "Liga 2 Perú",
    
    # === CONMEBOL ===
    "CLI": "Copa Libertadores", "CSA": "Copa Sudamericana",
    "CSUD": "Copa Sudamericana", "RECOPA": "Recopa Sudamericana",
    "SUDAMERICANO": "Sudamericano Sub-20", "SUDAMERICANO_U20": "Sudamericano Sub-20",
    
    # === NORTE/CENTROAMÉRICA ===
    "MX": "Liga MX", "MX_B": "Liga Expansión MX",
    "MX_C": "Liga Premier MX", "COPA_MX": "Copa MX",
    "MLS": "MLS", "USL": "USL Championship",
    "USL1": "USL League One", "NASL": "NASL",
    "CAN": "Canadian Premier League", "CAN_PL": "Canadian Premier League",
    "CRC": "Primera División Costa Rica", "GT": "Liga Nacional Guatemala",
    "HN": "Liga Nacional Honduras", "SV": "Primera División El Salvador",
    "PA": "LPF Panamá", "JM": "Premier League Jamaica",
    "NI": "Primera División Nicaragua", "CU": "Campeonato Nacional Cuba",
    
    # === CONCACAF ===
    "GOLD": "Copa Oro", "CCL": "Concacaf Champions League",
    "LEAGUES_CUP": "Leagues Cup", "NATIONS_CA": "Nations League CONCACAF",
    "COPA_ORO": "Copa Oro",
    
    # === ASIA ===
    "JP": "J1 League", "JP_B": "J2 League", "JP_C": "J3 League",
    "JP_LC": "J.League Cup", "KR": "K League 1", "KR_B": "K League 2",
    "KR_C": "K3 League", "CN": "Super League China", "CN_B": "China League One",
    "CN_C": "China League Two", "TH": "Thai League 1", "TH_B": "Thai League 2",
    "IDN": "Liga 1 Indonesia", "MYS": "Super League Malasia",
    "SGP": "Premier League Singapur", "VNM": "V.League 1",
    "PH": "Philippines Football League", "MM": "Myanmar National League",
    "KH": "Cambodian Premier League", "LA": "Lao Premier League",
    "IR": "Persian Gulf Pro League", "IQ": "Iraqi Premier League",
    "JO": "Jordanian Pro League", "LB": "Lebanese Premier League",
    "SY": "Syrian Premier League", "YE": "Yemeni League",
    "SA_A": "Pro League Saudi", "QA": "Stars League Qatar",
    "AE": "UAE Pro League", "KW": "Kuwait Premier League",
    "BH": "Bahraini Premier League", "OM": "Oman Professional League",
    "UZ": "Super League Uzbekistán", "KG": "Premier League Kirguistán",
    "TJ": "Tajikistan League", "TM": "Turkmenistan League",
    "IN": "ISL India", "BD": "Bangladesh Premier League",
    "PK": "Pakistan Premier League", "LK": "Sri Lanka Premier League",
    "NP": "Martyr's Memorial A-Division", "BT": "Bhutan Premier League",
    "MV": "Dhivehi Premier League", "AU_A": "A-League",
    "AU_B": "NPL Australia", "NZ": "National League Nueva Zelanda",
    
    # === AFC ===
    "ACL": "AFC Champions League Elite", "ACL2": "AFC Champions League Two",
    "AFC_CUP": "AFC Cup", "ASIA": "Copa Asiática",
    "ASIA_U23": "Copa Asiática U23",
    
    # === ÁFRICA ===
    "EG": "Premier League Egypt", "EG_B": "Second Division Egypt",
    "EG_C": "Third Division Egypt", "ZA": "Premier Division RSA",
    "ZA_B": "National First Division RSA", "MA": "Botola Pro",
    "TN": "Ligue 1 Túnez", "DZ": "Ligue 1 Argelia",
    "NG": "NPFL Nigeria", "GH": "Premier League Ghana",
    "CI": "Ligue 1 Costa de Marfil", "SN": "Ligue 1 Senegal",
    "CM": "Elite One Camerún", "AO": "Girabola Angola",
    "MZ": "Moçambola Mozambique", "ZM": "Super League Zambia",
    "ZW": "Premier Soccer League Zimbabwe", "BW": "Botswana Premier League",
    "NA": "Namibia Premier League", "SZ": "Eswatini Premier League",
    "LS": "Lesotho Premier League", "ET": "Ethiopian Premier League",
    "SD": "Sudan Premier League", "SS": "South Sudan League",
    "UG": "Uganda Premier League", "KE": "Kenyan Premier League",
    "TZ": "Tanzania Premier League", "RW": "Rwanda Premier League",
    "BI": "Burundi Premier League", "CD": "Linafoot RDC",
    "CG": "Congo Ligue 1", "GA": "Gabon Championnat National",
    "GQ": "Equatoguinean Premier League", "ST": "São Tomé Championship",
    "TD": "Chad Premier League", "CF": "Central African League",
    "BJ": "Benin Premier League", "TG": "Togo Championnat National",
    "BF": "Burkinabé Premier League", "ML": "Malian Première Division",
    "NE": "Niger Premier League", "MR": "Mauritanian Premier League",
    "GN": "Guinée Championnat National", "GW": "Guinea-Bissau League",
    "SL": "Sierra Leone National Premier League", "LR": "Liberia First Division",
    "GM": "GFA League First Division", "CV": "Campeonato Nacional Cabo Verde",
    "DJ": "Djibouti Premier League", "ER": "Eritrean Premier League",
    "SO": "Somali First Division", "MG": "THB Champions League Madagascar",
    "KM": "Comoros Premier League", "MU": "Mauritian Premier League",
    "SC_AFR": "Seychelles First Division", "RE": "Réunion Premier League",
    
    # === CAF ===
    "AFCON": "Africa Cup of Nations", "AFCON_U23": "Africa Cup U23",
    "AFCON_U20": "Africa Cup U20", "CAF_CL": "CAF Champions League",
    "CAF_CC": "CAF Confederation Cup", "CAF_SC": "CAF Super Cup",
    
    # === OCEANÍA ===
    "OFC": "OFC Nations Cup", "OFC_U20": "OFC U20 Championship",
    "FIJI": "Fiji Premier League", "PNG": "Papua New Guinea NSL",
    "SOL": "Solomon Islands S-League", "VAN": "Vanuatu Premia Divisen",
    "NCL": "New Caledonia Super Ligue", "TAH": "Tahiti Ligue 1",
    "SAM": "Samoa National League", "TGA": "Tonga Major League",
    
    # === MUNDIALES ===
    "WC": "World Cup", "EURO": "Euro", "COPA": "Copa América",
    "NATIONS": "Nations League", "WCC": "FIFA Club World Cup",
    "CONFED": "Confederations Cup", "OLYMPICS": "Olympic Football",
    "OLYMPICS_W": "Olympic Football Women", "U20_WC": "U20 World Cup",
    "U17_WC": "U17 World Cup",
    
    # === UEFA ===
    "CL": "Champions League", "EL": "Europa League",
    "ECL": "Conference League", "SUPER_CUP_UEFA": "UEFA Super Cup",
    "YOUTH_LEAGUE": "UEFA Youth League", "UEFA_NATIONS": "Nations League",
    
    # === AMISTOSOS ===
    "FRIENDLY_INT": "Amistoso Internacional", "FRIENDLY_CLUB": "Amistoso Club",
}

DEFAULT_COMPETITIONS = [
    # === TOP 5 + competiciones principales ===
    "PD", "PL", "SA", "BL1", "FL1", "PPL", "DED", "BSA", "CL", "EL",
    "ARG", "COL", "MX", "MLS", "JP", "KR", "SA_A", "EG", "ZA", "MA",
    "BE", "CH", "AU", "DK", "NO", "FI", "CZ", "GR", "TR", "UA",
    "HR", "RO", "SC", "RU", "PLN", "ECU", "PER", "CHI", "URU", "PAR",
    "VEN", "BOL", "CRC", "GT", "HN", "SV", "PA", "JM", "USL", "CAN",
    "IR", "QA", "AE", "IDN", "MYS", "SGP", "VNM", "ECL", "NATIONS",
    "AFCON", "COPA", "GOLD", "ASIA", "BRA_B", "ARG_B", "MX_B", "JP_B",
    "KR_B", "CN", "AU_A", "IN", "TH", "NG", "GH", "TN", "DZ", "ELC",
    "SP", "SI", "SD", "FL2", "WC", "EURO", "WCC",
    
    # === NUEVAS LIGAS ===
    # Europa Oriental
    "RS", "BG", "HU", "SK", "BA", "MK", "ME", "AL", "MD", "EE",
    "LV", "LT", "BY", "KZ", "AM", "GE", "AZ", "UZ", "KG",
    
    # Asia
    "JP_C", "KR_C", "CN_B", "CN_C", "TH_B", "PH", "MM", "KH", "LA",
    "IQ", "JO", "LB", "SY", "YE", "KW", "BH", "OM", "TJ", "TM",
    "BD", "PK", "LK", "NP", "BT", "MV", "AU_B", "NZ",
    
    # África
    "EG_B", "ZA_B", "CI", "SN", "CM", "AO", "MZ", "ZM", "ZW",
    "BW", "NA", "SZ", "LS", "ET", "SD", "SS", "UG", "KE", "TZ",
    "RW", "BI", "CD", "CG", "GA", "GQ", "ST", "TD", "CF",
    "BJ", "TG", "BF", "ML", "NE", "MR", "GN", "GW", "SL",
    "LR", "GM", "CV", "DJ", "ER", "SO", "MG", "KM", "MU",
    "SC_AFR", "RE",
    
    # Sudamérica
    "BRA_C", "BRA_D", "ARG_C", "COL_B", "CHI_B", "URU_B", "PAR_B",
    "VEN_B", "BOL_B", "ECU_B", "PER_B", "RECOPA", "SUDAMERICANO",
    
    # Norteamérica
    "MX_C", "USL1", "NASL", "NI", "CU",
    
    # Copa Nacional
    "CDR", "COPA_ESP", "TACA_POR", "COUPE_FR", "DFB_POKAL",
    "COPA_ITA", "FA_CUP", "EFL_CUP", "CDB", "COPA_ARG",
    "COPA_MX", "CCL", "LEAGUES_CUP",
    
    # Oceanía
    "FIJI", "PNG", "SOL", "VAN", "NCL", "TAH", "SAM", "TGA",
    
    # Internacional
    "CONFED", "OLYMPICS", "OLYMPICS_W", "U20_WC", "U17_WC",
    "YOUTH_LEAGUE", "SUPER_CUP_UEFA", "SUPER_ESP", "SUPER_POR",
    "TROPHEE", "SUPER_CUP_GER", "SUPER_ITA", "COMM_SHIELD",
    "CAF_CL", "CAF_CC", "CAF_SC", "ACL", "ACL2", "ASIA_U23",
    "AFCON_U23", "AFCON_U20", "NATIONS_CA", "OFC", "OFC_U20",
]


def cache_get(key, ttl=3600):
    if key in CACHE:
        data, ts = CACHE[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None


def cache_set(key, data):
    CACHE[key] = (data, datetime.now())


def api_get(endpoint, params=None, cache_key=None, ttl=3600):
    if cache_key:
        cached = cache_get(cache_key, ttl)
        if cached is not None:
            return cached

    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}/"
        logger.info(f"API CALL: {url} | params={params}")
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)

        if resp.status_code == 429:
            logger.warning("RATE LIMIT API-Football")
            return None
        if resp.status_code in (401, 403):
            logger.error(f"AUTH ERROR {resp.status_code}: {resp.text[:200]}")
            return None

        resp.raise_for_status()
        data = resp.json()

        if data.get("errors"):
            logger.error(f"API-Football errors: {data['errors']}")
            return None

        if cache_key:
            cache_set(cache_key, data)

        return data
    except Exception as e:
        logger.error(f"API error: {e}")
        return None


def safe_get(d, *keys, default=None):
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def parse_score_value(v):
    if v == "" or v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def get_league_id(competition_code):
    return LEAGUE_IDS.get(competition_code)


def get_season():
    now = datetime.now(timezone.utc)
    if now.month >= 7:
        return now.year
    else:
        return now.year - 1


# ============================================================
# OBTENER ESTADÍSTICAS DE UN PARTIDO ESPECÍFICO
# ============================================================

def get_fixture_statistics(fixture_id):
    if not fixture_id:
        return {}

    data = api_get(
        "fixtures/statistics",
        params={"fixture": fixture_id},
        cache_key=f"fixture_stats_{fixture_id}",
        ttl=86400
    )

    if not data or not isinstance(data, dict):
        return {}

    result = {}
    for item in data.get("response", []):
        team_id = safe_get(item, "team", "id")
        stats_list = item.get("statistics", [])

        parsed = {}
        for stat in stats_list:
            stat_type = stat.get("type", "").strip()
            value = stat.get("value")
            parsed[stat_type] = value

        if team_id:
            result[team_id] = parsed

    return result


def get_fixture_events(fixture_id):
    if not fixture_id:
        return []

    data = api_get(
        "fixtures/events",
        params={"fixture": fixture_id},
        cache_key=f"fixture_events_{fixture_id}",
        ttl=86400
    )

    if not data or not isinstance(data, dict):
        return []

    return data.get("response", [])


def count_events_for_team(events, team_id, event_types):
    count = 0
    for event in events:
        if event.get("team", {}).get("id") == team_id:
            if event.get("type") in event_types:
                count += 1
    return count


# ============================================================
# CALCULAR ESTADÍSTICAS REALES DESDE PARTIDOS JUGADOS
# ============================================================

def get_team_real_stats(team_id, league_id, season, max_fixtures=10):
    if not team_id or not league_id or not season:
        return None

    fixtures_data = api_get(
        "fixtures",
        params={
            "team": team_id,
            "league": league_id,
            "season": season,
            "last": max_fixtures,
            "status": "ft"
        },
        cache_key=f"team_fixtures_ft_{team_id}_{league_id}_{season}_{max_fixtures}",
        ttl=3600
    )

    if not fixtures_data or not isinstance(fixtures_data, dict):
        return None

    fixtures = fixtures_data.get("response", [])
    if not fixtures:
        return None

    total_gf = 0
    total_ga = 0
    total_corners = 0
    total_yellow = 0
    total_red = 0
    total_shots = 0
    total_shots_on = 0
    total_possession = 0
    total_fouls = 0

    matches_with_stats = 0
    matches_with_goals = 0

    over_15_count = 0
    over_25_count = 0
    over_35_count = 0
    btts_count = 0
    clean_sheet_count = 0
    failed_score_count = 0

    corners_matches = 0
    corners_over_45 = 0
    corners_over_55 = 0
    corners_over_65 = 0
    corners_over_75 = 0
    corners_over_85 = 0
    corners_over_95 = 0
    corners_over_105 = 0

    cards_matches = 0
    cards_over_15 = 0
    cards_over_25 = 0
    cards_over_35 = 0
    cards_over_45 = 0
    cards_over_55 = 0

    for fixture in fixtures:
        fixture_id = safe_get(fixture, "fixture", "id")
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})

        home_team = teams.get("home", {})
        away_team = teams.get("away", {})
        is_home = home_team.get("id") == team_id

        home_goals = goals.get("home", 0) or 0
        away_goals = goals.get("away", 0) or 0

        if is_home:
            gf = home_goals
            ga = away_goals
        else:
            gf = away_goals
            ga = home_goals

        total_goals = gf + ga

        total_gf += gf
        total_ga += ga
        matches_with_goals += 1

        if total_goals > 1.5:
            over_15_count += 1
        if total_goals > 2.5:
            over_25_count += 1
        if total_goals > 3.5:
            over_35_count += 1
        if gf > 0 and ga > 0:
            btts_count += 1
        if ga == 0:
            clean_sheet_count += 1
        if gf == 0:
            failed_score_count += 1

        fixture_stats = get_fixture_statistics(fixture_id)
        team_stats = fixture_stats.get(team_id, {})

        has_stats = False
        match_corners = None
        match_yellow = None
        match_red = None

        if team_stats:
            corners = team_stats.get("Corner Kicks")
            if corners is not None:
                try:
                    match_corners = int(corners)
                    total_corners += match_corners
                    has_stats = True
                except:
                    pass

            yellow = team_stats.get("Yellow Cards")
            if yellow is not None:
                try:
                    match_yellow = int(yellow)
                    total_yellow += match_yellow
                    has_stats = True
                except:
                    pass

            red = team_stats.get("Red Cards")
            if red is not None:
                try:
                    match_red = int(red)
                    total_red += match_red
                    has_stats = True
                except:
                    pass

            shots = team_stats.get("Total Shots")
            if shots is not None:
                try:
                    total_shots += int(shots)
                    has_stats = True
                except:
                    pass

            shots_on = team_stats.get("Shots on Goal")
            if shots_on is not None:
                try:
                    total_shots_on += int(shots_on)
                    has_stats = True
                except:
                    pass

            possession = team_stats.get("Ball Possession")
            if possession is not None:
                try:
                    if isinstance(possession, str):
                        possession = int(possession.replace("%", "").strip())
                    total_possession += int(possession)
                    has_stats = True
                except:
                    pass

            fouls = team_stats.get("Fouls")
            if fouls is not None:
                try:
                    total_fouls += int(fouls)
                    has_stats = True
                except:
                    pass

        if match_yellow is None or match_red is None:
            events = get_fixture_events(fixture_id)
            if events:
                yellow_count = sum(1 for e in events
                    if e.get("team", {}).get("id") == team_id
                    and e.get("type") == "Card"
                    and e.get("detail") == "Yellow Card")
                red_count = sum(1 for e in events
                    if e.get("team", {}).get("id") == team_id
                    and e.get("type") == "Card"
                    and e.get("detail") == "Red Card")

                if match_yellow is None:
                    match_yellow = yellow_count
                    total_yellow += match_yellow
                if match_red is None:
                    match_red = red_count
                    total_red += match_red
                has_stats = True

        if match_corners is not None:
            corners_matches += 1
            if match_corners > 4.5:
                corners_over_45 += 1
            if match_corners > 5.5:
                corners_over_55 += 1
            if match_corners > 6.5:
                corners_over_65 += 1
            if match_corners > 7.5:
                corners_over_75 += 1
            if match_corners > 8.5:
                corners_over_85 += 1
            if match_corners > 9.5:
                corners_over_95 += 1
            if match_corners > 10.5:
                corners_over_105 += 1

        if match_yellow is not None and match_red is not None:
            total_cards = match_yellow + match_red
            cards_matches += 1
            if total_cards > 1.5:
                cards_over_15 += 1
            if total_cards > 2.5:
                cards_over_25 += 1
            if total_cards > 3.5:
                cards_over_35 += 1
            if total_cards > 4.5:
                cards_over_45 += 1
            if total_cards > 5.5:
                cards_over_55 += 1

        if has_stats:
            matches_with_stats += 1

    played = matches_with_goals
    if played == 0:
        return None

    avg_gf = round(total_gf / played, 2)
    avg_ga = round(total_ga / played, 2)
    avg_total = round((total_gf + total_ga) / played, 2)

    avg_corners = round(total_corners / corners_matches, 2) if corners_matches else 0
    avg_yellow = round(total_yellow / matches_with_stats, 2) if matches_with_stats else 0
    avg_red = round(total_red / matches_with_stats, 2) if matches_with_stats else 0
    avg_shots = round(total_shots / matches_with_stats, 2) if matches_with_stats else 0
    avg_shots_on = round(total_shots_on / matches_with_stats, 2) if matches_with_stats else 0
    avg_possession = round(total_possession / matches_with_stats, 2) if matches_with_stats else 0
    avg_fouls = round(total_fouls / matches_with_stats, 2) if matches_with_stats else 0

    over_15_pct = round((over_15_count / played) * 100, 1)
    over_25_pct = round((over_25_count / played) * 100, 1)
    over_35_pct = round((over_35_count / played) * 100, 1)
    btts_pct = round((btts_count / played) * 100, 1)
    clean_sheet_pct = round((clean_sheet_count / played) * 100, 1)
    failed_score_pct = round((failed_score_count / played) * 100, 1)

    corners_pct = {
        "over_4_5": round((corners_over_45 / corners_matches) * 100, 1) if corners_matches else 0,
        "over_5_5": round((corners_over_55 / corners_matches) * 100, 1) if corners_matches else 0,
        "over_6_5": round((corners_over_65 / corners_matches) * 100, 1) if corners_matches else 0,
        "over_7_5": round((corners_over_75 / corners_matches) * 100, 1) if corners_matches else 0,
        "over_8_5": round((corners_over_85 / corners_matches) * 100, 1) if corners_matches else 0,
        "over_9_5": round((corners_over_95 / corners_matches) * 100, 1) if corners_matches else 0,
        "over_10_5": round((corners_over_105 / corners_matches) * 100, 1) if corners_matches else 0,
        "matches": corners_matches,
    }

    cards_pct = {
        "over_1_5": round((cards_over_15 / cards_matches) * 100, 1) if cards_matches else 0,
        "over_2_5": round((cards_over_25 / cards_matches) * 100, 1) if cards_matches else 0,
        "over_3_5": round((cards_over_35 / cards_matches) * 100, 1) if cards_matches else 0,
        "over_4_5": round((cards_over_45 / cards_matches) * 100, 1) if cards_matches else 0,
        "over_5_5": round((cards_over_55 / cards_matches) * 100, 1) if cards_matches else 0,
        "matches": cards_matches,
    }

    logger.info(f"Team {team_id}: played={played}, corners_matches={corners_matches}, "
                f"cards_matches={cards_matches}, avg_corners={avg_corners}")

    return {
        "played": played,
        "goals_for": total_gf,
        "goals_against": total_ga,
        "avg_team_goals": avg_gf,
        "avg_conceded": avg_ga,
        "avg_total_goals": avg_total,
        "avg_corners": avg_corners,
        "avg_yellow_cards": avg_yellow,
        "avg_red_cards": avg_red,
        "avg_total_cards": round(avg_yellow + avg_red, 2),
        "avg_shots": avg_shots,
        "avg_shots_on": avg_shots_on,
        "avg_possession": avg_possession,
        "avg_fouls": avg_fouls,
        "over_1_5_pct": over_15_pct,
        "over_2_5_pct": over_25_pct,
        "over_3_5_pct": over_35_pct,
        "btts_pct": btts_pct,
        "clean_sheet_pct": clean_sheet_pct,
        "failed_to_score_pct": failed_score_pct,
        "matches_with_stats": matches_with_stats,
        "corners_pct": corners_pct,
        "cards_pct": cards_pct,
    }


# ============================================================
# PREDICCIONES
# ============================================================

def get_predictions(fixture_id):
    if not fixture_id:
        return None

    data = api_get(
        "predictions",
        params={"fixture": fixture_id},
        cache_key=f"predictions_{fixture_id}",
        ttl=3600
    )

    if not data or not isinstance(data, dict):
        return None

    response = data.get("response", [])
    if not response:
        return None

    pred = response[0] if isinstance(response, list) else response

    predictions = pred.get("predictions", {})
    comparison = pred.get("comparison", {})

    return {
        "winner": predictions.get("winner", {}).get("name", ""),
        "winner_comment": predictions.get("winner", {}).get("comment", ""),
        "under_over": predictions.get("under_over", ""),
        "advice": predictions.get("advice", ""),
        "percent_home": safe_get(comparison, "home", default=""),
        "percent_draw": safe_get(comparison, "draw", default=""),
        "percent_away": safe_get(comparison, "away", default="")
    }


# ============================================================
# FIXTURES POR FECHA
# ============================================================

def get_fixtures_by_date(date, league_id=None, season=None):
    params = {"date": date}
    if league_id:
        params["league"] = league_id
    if season:
        params["season"] = season

    data = api_get(
        "fixtures",
        params=params,
        cache_key=f"fixtures_{date}_{league_id or 'all'}",
        ttl=1800
    )

    if not data or not isinstance(data, dict):
        return []

    return data.get("response", [])


def format_fixture(f):
    fixture = f.get("fixture", {})
    teams = f.get("teams", {})
    goals = f.get("goals", {})
    league = f.get("league", {})

    home = teams.get("home", {})
    away = teams.get("away", {})

    status = fixture.get("status", {}).get("short", "NS")
    status_map = {
        "NS": "NS", "1H": "1H", "HT": "HT", "2H": "2H",
        "ET": "ET", "P": "PEN", "FT": "FT", "AET": "AET",
        "PEN": "PEN", "SUSP": "SUSP", "INT": "INT",
        "PST": "PST", "CANC": "CANC", "ABD": "ABD",
        "AWD": "AWD", "WO": "WO"
    }

    raw_matchday = league.get("round", "")
    matchday = 0
    if isinstance(raw_matchday, int):
        matchday = raw_matchday
    elif isinstance(raw_matchday, str):
        parts = raw_matchday.split("-")
        if parts:
            last_part = parts[-1].strip()
            try:
                matchday = int(last_part)
            except:
                matchday = 0

    return {
        "id": fixture.get("id"),
        "utcDate": fixture.get("date"),
        "matchDate": (fixture.get("date") or "")[:10],
        "status": status_map.get(status, status),
        "statusText": status,
        "minute": fixture.get("status", {}).get("elapsed", 0),
        "venue": fixture.get("venue", {}).get("name", ""),
        "matchday": matchday,
        "homeTeam": {
            "id": home.get("id"),
            "name": home.get("name", "Local"),
            "shortName": home.get("name", "Local")[:15],
            "crest": home.get("logo", "")
        },
        "awayTeam": {
            "id": away.get("id"),
            "name": away.get("name", "Visitante"),
            "shortName": away.get("name", "Visitante")[:15],
            "crest": away.get("logo", "")
        },
        "competition": {
            "id": league.get("id"),
            "name": league.get("name", ""),
            "code": ""
        },
        "league_name": league.get("name", ""),
        "country": league.get("country", ""),
        "homeScore": goals.get("home"),
        "awayScore": goals.get("away"),
        "halfTimeHome": None,
        "halfTimeAway": None,
        "api_football_fixture_id": fixture.get("id")
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/matches")
def api_matches(date: str = Query(None)):
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    season = get_season()
    collected = []
    found = []

    for code in DEFAULT_COMPETITIONS:
        league_id = get_league_id(code)
        if not league_id:
            continue

        fixtures = get_fixtures_by_date(date, league_id=league_id, season=season)

        if fixtures:
            comp_matches = [format_fixture(f) for f in fixtures]
            if comp_matches:
                collected.extend(comp_matches)
                found.append({"code": code, "name": COMPETITIONS.get(code, code)})

    seen = set()
    unique = []
    for m in collected:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)

    unique.sort(key=lambda x: x.get("utcDate", ""))

    return {
        "matches": unique,
        "requested_date": date,
        "source_date": date if unique else None,
        "is_exact": True,
        "competitions_found": found,
        "source": "api-football.com"
    }


@app.get("/api/analyze/{match_id}")
def analyze(
    match_id: int,
    home_id: int = Query(...),
    away_id: int = Query(...),
    competition_id: int = Query(...),
    home_team: str = Query("Local"),
    away_team: str = Query("Visitante"),
    home_short: str = Query("Local"),
    away_short: str = Query("Visitante"),
    home_logo: str = Query(""),
    away_logo: str = Query(""),
    league: str = Query(""),
    country: str = Query(""),
    date: str = Query(""),
    time: str = Query("--:--"),
    venue: str = Query(""),
    home_score: str = Query(""),
    away_score: str = Query(""),
    matchday: str = Query("0"),
    status: str = Query("SCHEDULED")
):
    logger.info(f"=== ANALYZE match_id={match_id}, home={home_team}({home_id}), away={away_team}({away_id}) ===")

    comp_code = None
    for code, name in COMPETITIONS.items():
        if name.lower() in (league or "").lower():
            comp_code = code
            break

    if not comp_code:
        for code, lid in LEAGUE_IDS.items():
            if lid == competition_id:
                comp_code = code
                break

    league_id = get_league_id(comp_code) if comp_code else competition_id
    season = get_season()

    logger.info(f"Comp: {comp_code}, League ID: {league_id}, Season: {season}")

    home_stats = get_team_real_stats(home_id, league_id, season, max_fixtures=10) if league_id else None
    away_stats = get_team_real_stats(away_id, league_id, season, max_fixtures=10) if league_id else None

    home_mode = "REAL" if (home_stats and home_stats["played"] > 0) else "NO_DATA"
    away_mode = "REAL" if (away_stats and away_stats["played"] > 0) else "NO_DATA"

    home_form_data = api_get(
        "teams/statistics",
        params={"team": home_id, "league": league_id, "season": season},
        cache_key=f"team_stats_form_{home_id}_{league_id}_{season}",
        ttl=7200
    )
    away_form_data = api_get(
        "teams/statistics",
        params={"team": away_id, "league": league_id, "season": season},
        cache_key=f"team_stats_form_{away_id}_{league_id}_{season}",
        ttl=7200
    )

    def parse_form(form_data):
        if not form_data or not isinstance(form_data, dict):
            return [], ""
        response = form_data.get("response", {})
        form_str = response.get("form", "") if isinstance(response, dict) else ""
        form_list = []
        for char in (form_str or "")[-5:]:
            if char == "W":
                form_list.append({"result": "W", "result_text": "Victoria"})
            elif char == "D":
                form_list.append({"result": "D", "result_text": "Empate"})
            elif char == "L":
                form_list.append({"result": "L", "result_text": "Derrota"})
        return form_list, form_str or ""

    home_form, home_form_str = parse_form(home_form_data)
    away_form, away_form_str = parse_form(away_form_data)

    if not home_stats or home_stats["played"] == 0:
        home_stats = {
            "played": 0, "goals_for": 0, "goals_against": 0,
            "avg_team_goals": 1.25, "avg_conceded": 1.25, "avg_total_goals": 2.5,
            "avg_corners": 4.5, "avg_yellow_cards": 2.0, "avg_red_cards": 0.15,
            "avg_total_cards": 2.15, "avg_shots": 10, "avg_shots_on": 4,
            "avg_possession": 50, "avg_fouls": 12,
            "over_1_5_pct": 70, "over_2_5_pct": 50, "over_3_5_pct": 25,
            "btts_pct": 50, "clean_sheet_pct": 20, "failed_to_score_pct": 20,
            "matches_with_stats": 0,
            "corners_pct": {
                "over_4_5": 0, "over_5_5": 0, "over_6_5": 0, "over_7_5": 0,
                "over_8_5": 0, "over_9_5": 0, "over_10_5": 0, "matches": 0
            },
            "cards_pct": {
                "over_1_5": 0, "over_2_5": 0, "over_3_5": 0, "over_4_5": 0,
                "over_5_5": 0, "matches": 0
            },
        }
        home_mode = "DEFAULT"

    if not away_stats or away_stats["played"] == 0:
        away_stats = {
            "played": 0, "goals_for": 0, "goals_against": 0,
            "avg_team_goals": 1.25, "avg_conceded": 1.25, "avg_total_goals": 2.5,
            "avg_corners": 4.5, "avg_yellow_cards": 2.0, "avg_red_cards": 0.15,
            "avg_total_cards": 2.15, "avg_shots": 10, "avg_shots_on": 4,
            "avg_possession": 50, "avg_fouls": 12,
            "over_1_5_pct": 70, "over_2_5_pct": 50, "over_3_5_pct": 25,
            "btts_pct": 50, "clean_sheet_pct": 20, "failed_to_score_pct": 20,
            "matches_with_stats": 0,
            "corners_pct": {
                "over_4_5": 0, "over_5_5": 0, "over_6_5": 0, "over_7_5": 0,
                "over_8_5": 0, "over_9_5": 0, "over_10_5": 0, "matches": 0
            },
            "cards_pct": {
                "over_1_5": 0, "over_2_5": 0, "over_3_5": 0, "over_4_5": 0,
                "over_5_5": 0, "matches": 0
            },
        }
        away_mode = "DEFAULT"

    predictions = get_predictions(match_id)

    probabilities = {
        "over_1_5": round((home_stats["over_1_5_pct"] + away_stats["over_1_5_pct"]) / 2, 1),
        "over_2_5": round((home_stats["over_2_5_pct"] + away_stats["over_2_5_pct"]) / 2, 1),
        "over_3_5": round((home_stats["over_3_5_pct"] + away_stats["over_3_5_pct"]) / 2, 1),
        "btts": round((home_stats["btts_pct"] + away_stats["btts_pct"]) / 2, 1),
        "total_expected_goals": round(home_stats["avg_team_goals"] + away_stats["avg_team_goals"], 2),
        "home_xg": 0,
        "away_xg": 0
    }

    odds = {"home": 0, "draw": 0, "away": 0}
    if predictions:
        try:
            odds["home"] = float(str(predictions.get("percent_home", "0")).replace("%", "")) / 100 if predictions.get("percent_home") else 0
            odds["draw"] = float(str(predictions.get("percent_draw", "0")).replace("%", "")) / 100 if predictions.get("percent_draw") else 0
            odds["away"] = float(str(predictions.get("percent_away", "0")).replace("%", "")) / 100 if predictions.get("percent_away") else 0
        except:
            pass

    return JSONResponse({
        "match_info": {
            "home_team": home_team,
            "away_team": away_team,
            "home_short": home_short,
            "away_short": away_short,
            "home_logo": home_logo,
            "away_logo": away_logo,
            "league": league,
            "country": country,
            "date": date,
            "time": time,
            "venue": venue,
            "status": status,
            "matchday": matchday,
            "home_score": parse_score_value(home_score),
            "away_score": parse_score_value(away_score)
        },
        "home_form": home_form,
        "away_form": away_form,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "predictions": predictions,
        "probabilities": probabilities,
        "odds": odds,
        "stats_available": bool(home_stats["played"] or away_stats["played"]),
        "debug": {
            "match_id": match_id,
            "home_id": home_id,
            "away_id": away_id,
            "competition_id": competition_id,
            "league_id_api_football": league_id,
            "comp_code": comp_code,
            "season": season,
            "home_mode_used": home_mode,
            "away_mode_used": away_mode,
            "home_stats_played": home_stats["played"],
            "away_stats_played": away_stats["played"]
        }
    })


@app.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "cache_size": len(CACHE),
        "api_football": "configured",
        "version": "12.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
