import os
import logging
from datetime import datetime, timedelta

import requests
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="TipFactory", version="9.0.0")

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

# === LIGAS SOPORTADAS (plan Pro = todas las disponibles) ===
# IDs oficiales de API-Football v3
LEAGUE_IDS = {
    # TOP 5 EUROPEAS
    "PL": 39,      # Premier League
    "PD": 140,     # La Liga
    "SA": 135,     # Serie A
    "BL1": 78,     # Bundesliga
    "FL1": 61,     # Ligue 1

    # OTRAS EUROPEAS
    "PPL": 94,     # Primeira Liga
    "DED": 88,     # Eredivisie
    "ELC": 40,     # Championship (ENG)
    "SB": 203,     # Superettan (SWE)
    "SP": 207,     # La Liga 2 (ESP) - CORREGIDO
    "SI": 131,     # Serie B (ITA)
    "SD": 81,      # 2. Bundesliga (GER)
    "FL2": 62,     # Ligue 2 (FRA)
    "PLN": 106,    # Ekstraklasa (POL)
    "RU": 235,     # Premier League (RUS)
    "BE": 144,     # Jupiler Pro League (BEL)
    "CH": 207,     # Super League (SUI) - CORREGIDO
    "AU": 218,     # Bundesliga (AUT)
    "DK": 119,     # Superliga (DEN)
    "NO": 103,     # Eliteserien (NOR)
    "FI": 244,     # Veikkausliiga (FIN)
    "CZ": 346,     # First League (CZE)
    "GR": 197,     # Super League (GRE) - CORREGIDO
    "TR": 203,     # Süper Lig (TUR) - CORREGIDO
    "UA": 333,     # Premier League (UKR)
    "HR": 210,     # HNL (CRO)
    "RO": 283,     # Liga I (ROU)
    "SC": 180,     # Premiership (SCO)
    "SPL": 179,    # Scottish Championship
    "NIR": 182,    # NIFL Premiership
    "IRL": 357,    # Premier Division (IRL)
    "SVK": 332,    # Super Liga (SVK)
    "SVN": 373,    # Prva Liga (SVN)
    "BGR": 172,    # First League (BGR)
    "SRB": 286,    # Super Liga (SRB)
    "HUN": 271,    # OTP Bank Liga (HUN)
    "ISR": 383,    # Ligat Ha'Al (ISR)
    "KAZ": 389,    # Premier League (KAZ)
    "MDA": 406,    # Super Liga (MDA)
    "GEO": 358,    # Erovnuli Liga (GEO)
    "ARM": 342,    # Premier League (ARM)
    "AZE": 391,    # Premier League (AZE)
    "EST": 332,    # Meistriliiga (EST)
    "LVA": 353,    # Virsliga (LVA)
    "LTU": 362,    # A Lyga (LTU)
    "FRO": 374,    # Premier League (FRO)
    "GIB": 384,    # National League (GIB)
    "MLT": 377,    # Premier League (MLT)
    "CYP": 148,    # First Division (CYP)
    "LUX": 214,    # National Division (LUX)
    "AND": 400,    # Primera Divisió (AND)
    "SMR": 388,    # Campionato (SMR)
    "LIE": 385,    # Premier League (LIE)
    "KOS": 394,    # Superliga (KOS)
    "MKD": 345,    # First League (MKD)
    "MNE": 360,    # First League (MNE)
    "ALB": 309,    # Superliga (ALB)
    "BIH": 318,    # Premier League (BIH)
    "WAL": 109,    # Cymru Premier (WAL)
    "GRL": 375,    # Premier League (GRL)
    "ISL": 166,    # Besta deild (ISL)

    # SUDAMÉRICA
    "BSA": 71,     # Brasileirao
    "CLI": 13,     # Copa Libertadores
    "CSA": 11,     # Copa Sudamericana
    "ARG": 128,    # Liga Profesional (ARG)
    "COL": 239,    # Primera A (COL)
    "CHI": 265,    # Primera División (CHI)
    "URU": 268,    # Primera División (URU)
    "PAR": 252,    # Primera División (PAR)
    "ECU": 242,    # Serie A (ECU)
    "PER": 281,    # Liga 1 (PER)
    "VEN": 277,    # Primera División (VEN)
    "BOL": 344,    # División Profesional (BOL)
    "BRA_B": 72,   # Serie B (BRA)
    "BRA_C": 73,   # Serie C (BRA)
    "BRA_D": 74,   # Serie D (BRA)
    "ARG_B": 129,  # Primera Nacional (ARG)
    "CHI_B": 266,  # Primera B (CHI)
    "URU_B": 269,  # Segunda División (URU)
    "COL_B": 240,  # Primera B (COL)
    "ECU_B": 243,  # Serie B (ECU)
    "PAR_B": 253,  # División Intermedia (PAR)
    "PER_B": 282,  # Liga 2 (PER)
    "VEN_B": 278,  # Segunda División (VEN)
    "BOL_B": 345,  # División Profesional B (BOL)
    "CHL_CUP": 44, # Copa Chile
    "ARG_CUP": 130, # Copa Argentina
    "BRA_CUP": 75,  # Copa do Brasil
    "URU_CUP": 270, # Copa Uruguay

    # CONCACAF
    "MLS": 253,    # Major League Soccer
    "MX": 262,     # Liga MX
    "CRC": 163,    # Primera División (CRC)
    "GT": 370,     # Liga Nacional (GUA)
    "HN": 300,     # Liga Nacional (HON)
    "SV": 279,     # Primera División (SLV)
    "PA": 287,     # LPF (PAN)
    "JM": 357,     # Premier League (JAM)
    "USL": 255,    # USL Championship
    "USL1": 256,   # USL League One
    "NASL": 257,   # NASL
    "MX_B": 263,   # Liga de Expansión MX
    "MX_ASC": 264, # Liga Premier MX
    "CAN": 259,    # Canadian Premier League
    "CUB": 372,    # Campeonato Nacional (CUB)
    "DOM": 373,    # Liga Dominicana (DOM)
    "NCA": 374,    # Primera División (NCA)
    "TRI": 375,    # TT Pro League (TRI)
    "HAI": 376,    # Ligue Haïtienne (HAI)
    "SKN": 377,    # SKNFA Premier League (SKN)
    "LCA": 378,    # SLFA First Division (LCA)
    "VIN": 379,    # Vincy Premier League (VIN)
    "BRB": 380,    # BFA Premier League (BRB)
    "GRN": 381,    # GFA Premier League (GRN)
    "ATG": 382,    # ABFA Premier League (ATG)
    "BER": 383,    # Bermudian Premier Division (BER)
    "CAY": 384,    # CIFA Premier League (CAY)
    "TCA": 385,    # Provo Premier League (TCA)
    "VIR": 386,    # U.S. Virgin Islands Championship (VIR)
    "PUR": 387,    # Liga Puerto Rico (PUR)
    "ARU": 388,    # Aruban Division di Honor (ARU)
    "BOE": 389,    # Bonaire League (BOE)
    "CUR": 390,    # Curaçao Promé Divishon (CUR)
    "SXM": 391,    # SXM Premier League (SXM)
    "MAF": 392,    # Saint-Martin Championship (MAF)
    "GUA": 393,    # Liga Nacional de Guatemala (GUA)

    # ASIA
    "JP": 98,      # J1 League (JPN)
    "KR": 292,     # K League 1 (KOR)
    "CN": 169,     # Super League (CHN)
    "AU_A": 113,   # A-League (AUS)
    "IN": 323,     # ISL (IND)
    "TH": 295,     # Thai League 1
    "SA_A": 307,   # Pro League (KSA)
    "AE": 301,     # UAE Pro League
    "QA": 340,     # Stars League (QAT)
    "IR": 291,     # Persian Gulf Pro League
    "JP_B": 99,    # J2 League (JPN)
    "JP_C": 100,   # J3 League (JPN)
    "KR_B": 293,   # K League 2 (KOR)
    "CN_B": 170,   # China League One (CHN)
    "IDN": 274,    # Liga 1 (IDN)
    "MYS": 274,    # Super League (MYS)
    "SGP": 275,    # Premier League (SGP)
    "VNM": 276,    # V.League 1 (VNM)
    "PHL": 277,    # Philippines Football League (PHL)
    "HKG": 278,    # Hong Kong Premier League (HKG)
    "TWN": 279,    # Taiwan Football Premier League (TWN)
    "MAC": 280,    # Liga de Elite (MAC)
    "BGD": 281,    # Bangladesh Premier League (BGD)
    "PAK": 282,    # Pakistan Premier League (PAK)
    "LKA": 283,    # Sri Lanka Champions League (LKA)
    "NEP": 284,    # Martyr's Memorial A-Division (NEP)
    "BHU": 285,    # Bhutan Premier League (BHU)
    "MDV": 286,    # Dhivehi Premier League (MDV)
    "KGZ": 287,    # Kyrgyz Premier League (KGZ)
    "TJK": 288,    # Tajikistan League (TJK)
    "TKM": 289,    # Ýokary Liga (TKM)
    "UZB": 290,    # Uzbekistan League (UZB)
    "AFG": 291,    # Afghan Premier League (AFG)
    "MNG": 292,    # Mongolian Premier League (MNG)
    "BRN": 293,    # Bahraini Premier League (BRN)
    "IRQ": 294,    # Iraqi Premier League (IRQ)
    "JOR": 295,    # Jordanian Pro League (JOR)
    "KUW": 296,    # Kuwaiti Premier League (KUW)
    "LBN": 297,    # Lebanese Premier League (LBN)
    "OMA": 298,    # Oman Professional League (OMA)
    "PLE": 299,    # West Bank Premier League (PLE)
    "SYR": 300,    # Syrian Premier League (SYR)
    "YEM": 301,    # Yemeni League (YEM)

    # ÁFRICA
    "EG": 233,     # Premier League (EGY)
    "ZA": 289,     # Premier Division (RSA)
    "MA": 200,     # Botola Pro (MAR)
    "TN": 194,     # Ligue 1 (TUN)
    "DZ": 186,     # Ligue 1 (ALG)
    "NG": 371,     # NPFL (NGA)
    "GH": 376,     # Premier League (GHA)
    "CIV": 377,    # Ligue 1 (CIV)
    "SEN": 378,    # Ligue 1 (SEN)
    "MLI": 379,    # Première Division (MLI)
    "BFA": 380,    # Première Division (BFA)
    "NER": 381,    # Championnat National (NER)
    "BEN": 382,    # Championnat National (BEN)
    "TGO": 383,    # Championnat National (TGO)
    "GIN": 384,    # Ligue 1 (GIN)
    "SLE": 385,    # Premier League (SLE)
    "LBR": 386,    # Premier League (LBR)
    "GAB": 387,    # Championnat National (GAB)
    "CMR": 388,    # Elite One (CMR)
    "CAF": 389,    # CAF Champions League
    "CAF_CC": 390, # CAF Confederation Cup
    "RSA_B": 391,  # National First Division (RSA)
    "MAR_B": 392,  # Botola 2 (MAR)
    "TUN_B": 393,  # Ligue 2 (TUN)
    "ALG_B": 394,  # Ligue 2 (ALG)
    "EGY_B": 395,  # Egyptian Second Division (EGY)
    "GHA_B": 396,  # Division One (GHA)
    "NGA_B": 397,  # Nigeria National League (NGA)
    "KEN": 398,    # Kenyan Premier League (KEN)
    "TAN": 399,    # Tanzanian Premier League (TAN)
    "UGA": 400,    # Uganda Premier League (UGA)
    "RWA": 401,    # Rwanda Premier League (RWA)
    "BDI": 402,    # Burundi Premier League (BDI)
    "ETH": 403,    # Ethiopian Premier League (ETH)
    "SOM": 404,    # Somali First Division (SOM)
    "DJI": 405,    # Djibouti Premier League (DJI)
    "ERI": 406,    # Eritrean Premier League (ERI)
    "SSD": 407,    # South Sudan Football Championship (SSD)
    "ZAM": 408,    # Super League (ZAM)
    "ZIM": 409,    # Premier Soccer League (ZIM)
    "MWI": 410,    # Super League (MWI)
    "MOZ": 411,    # Moçambola (MOZ)
    "ANG": 412,    # Girabola (ANG)
    "COD": 413,    # Linafoot (COD)
    "CGO": 414,    # Ligue 1 (CGO)
    "GAB_B": 415,  # D2 (GAB)
    "EQG": 416,    # Liga Nacional (EQG)
    "STP": 417,    # Campeonato Nacional (STP)
    "CHA": 418,    # Chad Premier League (CHA)
    "CAF": 419,    # CAF Champions League
    "CAF_CC": 420, # CAF Confederation Cup

    # OCEANÍA
    "NZL": 421,    # New Zealand National League (NZL)
    "AUS_NPL": 422, # National Premier Leagues (AUS)
    "PNG": 423,    # Papua New Guinea National Soccer League (PNG)
    "FIJ": 424,    # Fiji Premier League (FIJ)
    "SOL": 425,    # Solomon Islands S-League (SOL)
    "VAN": 426,    # Vanuatu Premia Divisen (VAN)
    "NCL": 427,    # New Caledonia Super Ligue (NCL)
    "TAH": 428,    # Tahiti Ligue 1 (TAH)
    "SAM": 429,    # Samoa National League (SAM)
    "TGA": 430,    # Tonga Major League (TGA)
    "COK": 431,    # Cook Islands Round Cup (COK)
    "NIU": 432,    # Niue Soccer Tournament (NIU)
    "KIR": 433,    # Kiribati National Championship (KIR)
    "NRU": 434,    # Nauru Soccer League (NRU)
    "TUV": 435,    # Tuvalu A-Division (TUV)
    "PLW": 436,    # Palau Soccer League (PLW)
    "FSM": 437,    # FSM National League (FSM)
    "MHL": 438,    # Marshall Islands Soccer League (MHL)

    # INTERNACIONAL
    "CL": 2,       # Champions League
    "EL": 3,       # Europa League
    "ECL": 848,    # Conference League
    "WC": 1,       # World Cup
    "EURO": 4,     # European Championship
    "COPA": 9,     # Copa América
    "AFCON": 6,    # Africa Cup of Nations
    "GOLD": 22,    # Gold Cup
    "ASIA": 7,     # Asian Cup
    "NATIONS": 5,  # UEFA Nations League
    "WCC": 10,     # FIFA Club World Cup
    "UEL": 11,     # UEFA Super Cup
    "REC": 12,     # Recopa Sudamericana
    "SUD": 13,     # Copa Libertadores
    "SUD2": 14,    # Copa Sudamericana
    "AFC_CL": 15,  # AFC Champions League
    "AFC_CC": 16,  # AFC Cup
    "CAF_CL": 17,  # CAF Champions League
    "CAF_CC2": 18, # CAF Confederation Cup
    "CONCAF_CL": 19, # CONCACAF Champions League
    "CONCAF_CC": 20, # CONCACAF League
    "OFC_CL": 21,  # OFC Champions League
    "WOMEN_WC": 23, # FIFA Women's World Cup
    "WOMEN_EURO": 24, # UEFA Women's Euro
    "WOMEN_COPA": 25, # Copa América Femenina
    "WOMEN_AFCON": 26, # Africa Women Cup of Nations
    "WOMEN_ASIA": 27, # AFC Women's Asian Cup
    "WOMEN_GOLD": 28, # CONCACAF W Championship
    "WOMEN_OFC": 29,  # OFC Women's Nations Cup
    "OLY": 30,      # Olympic Games
    "U20_WC": 31,   # FIFA U-20 World Cup
    "U17_WC": 32,   # FIFA U-17 World Cup
    "U21_EURO": 33, # UEFA U-21 Championship
    "U19_EURO": 34, # UEFA U-19 Championship
    "U17_EURO": 35, # UEFA U-17 Championship
    "U20_AFCON": 36, # Africa U-20 Cup of Nations
    "U17_AFCON": 37, # Africa U-17 Cup of Nations
    "U23_ASIA": 38,  # AFC U-23 Asian Cup
    "U20_ASIA": 39,  # AFC U-20 Asian Cup
    "U17_ASIA": 40,  # AFC U-17 Asian Cup
    "U20_CONCAF": 41, # CONCACAF U-20 Championship
    "U17_CONCAF": 42, # CONCACAF U-17 Championship
    "U20_SUD": 43,   # CONMEBOL U-20
    "U17_SUD": 44,   # CONMEBOL U-17
    "U20_OFC": 45,   # OFC U-20 Championship
    "U17_OFC": 46,   # OFC U-17 Championship
    "FUTSAL_WC": 47, # FIFA Futsal World Cup
    "BEACH_WC": 48,  # FIFA Beach Soccer World Cup
}

COMPETITIONS = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "PPL": "Primeira Liga",
    "DED": "Eredivisie",
    "ELC": "Championship",
    "SP": "La Liga 2",
    "SI": "Serie B",
    "SD": "2. Bundesliga",
    "FL2": "Ligue 2",
    "BSA": "Brasileirao",
    "CLI": "Copa Libertadores",
    "CSA": "Copa Sudamericana",
    "ARG": "Liga Argentina",
    "COL": "Liga Colombia",
    "MX": "Liga MX",
    "MLS": "MLS",
    "JP": "J1 League",
    "KR": "K League",
    "SA_A": "Pro League Saudi",
    "EG": "Premier League Egypt",
    "WC": "World Cup",
    "EURO": "Euro",
    "CL": "Champions League",
    "EL": "Europa League",
    "ECL": "Conference League",
    "NATIONS": "Nations League",
    "AFCON": "Africa Cup",
    "COPA": "Copa América",
    "GOLD": "Gold Cup",
    "ASIA": "Asian Cup",
    "BRA_B": "Série B Brasil",
    "BRA_C": "Série C Brasil",
    "ARG_B": "Primera Nacional",
    "MX_B": "Liga Expansión MX",
    "JP_B": "J2 League",
    "KR_B": "K League 2",
    "CN": "Super League China",
    "AU_A": "A-League",
    "IN": "ISL India",
    "TH": "Thai League",
    "ZA": "Premier Division RSA",
    "MA": "Botola Pro",
    "TN": "Ligue 1 Túnez",
    "DZ": "Ligue 1 Argelia",
    "NG": "NPFL Nigeria",
    "GH": "Premier League Ghana",
    "BE": "Jupiler Pro League",
    "CH": "Super League Suiza",
    "AU": "Bundesliga Austria",
    "DK": "Superliga Dinamarca",
    "NO": "Eliteserien",
    "FI": "Veikkausliiga",
    "CZ": "First League Checa",
    "GR": "Super League Grecia",
    "TR": "Süper Lig",
    "UA": "Premier League Ucrania",
    "HR": "HNL Croacia",
    "RO": "Liga I Rumanía",
    "SC": "Premiership Escocia",
    "RU": "Premier League Rusia",
    "PLN": "Ekstraklasa Polonia",
    "ECU": "Serie A Ecuador",
    "PER": "Liga 1 Perú",
    "CHI": "Primera División Chile",
    "URU": "Primera División Uruguay",
    "PAR": "Primera División Paraguay",
    "VEN": "Primera División Venezuela",
    "BOL": "División Profesional Bolivia",
    "CRC": "Primera División Costa Rica",
    "GT": "Liga Nacional Guatemala",
    "HN": "Liga Nacional Honduras",
    "SV": "Primera División El Salvador",
    "PA": "LPF Panamá",
    "JM": "Premier League Jamaica",
    "USL": "USL Championship",
    "CAN": "Canadian Premier League",
    "IR": "Persian Gulf Pro League",
    "QA": "Stars League Qatar",
    "AE": "UAE Pro League",
    "IDN": "Liga 1 Indonesia",
    "MYS": "Super League Malasia",
    "SGP": "Premier League Singapur",
    "VNM": "V.League 1",
    "HKG": "Hong Kong Premier League",
    "TWN": "Taiwan Football Premier League",
    "KEN": "Kenyan Premier League",
    "TAN": "Tanzanian Premier League",
    "UGA": "Uganda Premier League",
    "ZAM": "Super League Zambia",
    "ZIM": "Premier Soccer League Zimbabwe",
    "CIV": "Ligue 1 Costa de Marfil",
    "SEN": "Ligue 1 Senegal",
    "WCC": "FIFA Club World Cup",
    "UEL": "UEFA Super Cup",
    "REC": "Recopa Sudamericana",
    "AFC_CL": "AFC Champions League",
    "CAF_CL": "CAF Champions League",
    "CONCAF_CL": "CONCACAF Champions League",
    "OFC_CL": "OFC Champions League",
    "WOMEN_WC": "Women's World Cup",
    "WOMEN_EURO": "Women's Euro",
    "OLY": "Olympic Games",
    "U20_WC": "U-20 World Cup",
    "U17_WC": "U-17 World Cup",
    "FUTSAL_WC": "Futsal World Cup",
    "BEACH_WC": "Beach Soccer World Cup",
}

# Ligas que aparecen por defecto en los filtros
DEFAULT_COMPETITIONS = [
    "PD", "PL", "SA", "BL1", "FL1", "PPL", "DED", "BSA", "CL", "EL",
    "ARG", "COL", "MX", "MLS", "JP", "KR", "SA_A", "EG", "ZA", "MA",
    "BE", "CH", "AU", "DK", "NO", "FI", "CZ", "GR", "TR", "UA",
    "HR", "RO", "SC", "RU", "PLN", "ECU", "PER", "CHI", "URU", "PAR",
    "VEN", "BOL", "CRC", "GT", "HN", "SV", "PA", "JM", "USL", "CAN",
    "IR", "QA", "AE", "IDN", "MYS", "SGP", "VNM", "HKG", "TWN", "KEN",
    "TAN", "UGA", "ZAM", "ZIM", "CIV", "SEN", "WCC", "UEL", "REC", "AFC_CL",
    "CAF_CL", "CONCAF_CL", "OFC_CL", "WOMEN_WC", "WOMEN_EURO", "OLY", "U20_WC",
    "U17_WC", "FUTSAL_WC", "BEACH_WC", "NATIONS", "AFCON", "COPA", "GOLD", "ASIA",
    "BRA_B", "BRA_C", "ARG_B", "MX_B", "JP_B", "KR_B", "CN", "AU_A", "IN", "TH",
    "NG", "GH", "TN", "DZ", "ELC", "SP", "SI", "SD", "FL2", "SPL",
    "NIR", "IRL", "SVK", "SVN", "BGR", "SRB", "HUN", "ISR", "KAZ", "MDA",
    "GEO", "ARM", "AZE", "EST", "LVA", "LTU", "FRO", "GIB", "MLT", "CYP",
    "LUX", "AND", "SMR", "LIE", "KOS", "MKD", "MNE", "ALB", "BIH", "WAL",
    "GRL", "ISL", "BRA_CUP", "ARG_CUP", "CHL_CUP", "URU_CUP",
]


def cache_get(key, ttl=1800):
    if key in CACHE:
        data, ts = CACHE[key]
        if (datetime.now() - ts).seconds < ttl:
            return data
    return None


def cache_set(key, data):
    CACHE[key] = (data, datetime.now())


def api_get(endpoint, params=None, cache_key=None, ttl=1800):
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
    """Determina la temporada actual (2024 para 2024-2025)"""
    now = datetime.utcnow()
    if now.month >= 7:
        return now.year
    else:
        return now.year - 1


def get_team_stats(team_id, league_id, season):
    """
    Obtiene estadísticas de equipo desde API-Football v3
    Endpoint: /teams/statistics?team={id}&league={id}&season={year}
    """
    if not team_id or not league_id or not season:
        return None

    data = api_get(
        "teams/statistics",
        params={"team": team_id, "league": league_id, "season": season},
        cache_key=f"team_stats_{team_id}_{league_id}_{season}",
        ttl=3600
    )

    if not data or not isinstance(data, dict):
        return None

    response = data.get("response", {})
    if not response:
        return None

    fixtures = response.get("fixtures", {})
    goals = response.get("goals", {})
    biggest = response.get("biggest", {})
    clean_sheet = response.get("clean_sheet", {})
    failed_to_score = response.get("failed_to_score", {})
    form = response.get("form", "")

    # Extraer estadísticas de corners y tarjetas si están disponibles
    lineups = response.get("lineups", [])
    cards = response.get("cards", {})

    # Intentar obtener corners desde diferentes ubicaciones posibles
    corners = 0
    if isinstance(response.get("corners"), dict):
        corners = response.get("corners", {}).get("total", 0)

    # Tarjetas
    yellow_cards = 0
    red_cards = 0
    if isinstance(cards, dict):
        yellow_cards = cards.get("yellow", {}).get("total", 0) if isinstance(cards.get("yellow"), dict) else 0
        red_cards = cards.get("red", {}).get("total", 0) if isinstance(cards.get("red"), dict) else 0

    played = safe_get(fixtures, "played", "total", default=0)
    wins = safe_get(fixtures, "wins", "total", default=0)
    draws = safe_get(fixtures, "draws", "total", default=0)
    losses = safe_get(fixtures, "loses", "total", default=0)

    goals_for = safe_get(goals, "for", "total", "total", default=0)
    goals_against = safe_get(goals, "against", "total", "total", default=0)

    avg_gf = round(goals_for / played, 2) if played else 0
    avg_ga = round(goals_against / played, 2) if played else 0
    avg_total = round((goals_for + goals_against) / played, 2) if played else 0

    form_list = []
    for char in (form or "")[-5:]:
        if char == "W":
            form_list.append({"result": "W", "result_text": "Victoria"})
        elif char == "D":
            form_list.append({"result": "D", "result_text": "Empate"})
        elif char == "L":
            form_list.append({"result": "L", "result_text": "Derrota"})

    est_over_15 = min(100, round(avg_total * 35, 1))
    est_over_25 = min(100, round(avg_total * 25, 1))
    est_over_35 = min(100, round(avg_total * 15, 1))
    est_btts = min(100, round((avg_gf / max(avg_gf + 0.5, 0.1)) * (avg_ga / max(avg_ga + 0.5, 0.1)) * 100, 1))

    clean_sheets = clean_sheet.get("total", 0) if isinstance(clean_sheet, dict) else 0
    failed_scores = failed_to_score.get("total", 0) if isinstance(failed_to_score, dict) else 0

    return {
        "played": played,
        "won": wins,
        "draw": draws,
        "lost": losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "avg_total_goals": avg_total,
        "avg_team_goals": avg_gf,
        "avg_conceded": avg_ga,
        "btts_pct": est_btts,
        "over_1_5_pct": est_over_15,
        "over_2_5_pct": est_over_25,
        "over_3_5_pct": est_over_35,
        "clean_sheet_pct": round((clean_sheets / played) * 100, 1) if played else 0,
        "failed_to_score_pct": round((failed_scores / played) * 100, 1) if played else 0,
        "form_string": form or "",
        "form": form_list,
        "biggest_win": safe_get(biggest, "wins", default=""),
        "biggest_loss": safe_get(biggest, "loses", default=""),
        # Nuevos campos para corners y tarjetas
        "corners_total": corners,
        "yellow_cards": yellow_cards,
        "red_cards": red_cards,
        "avg_corners": round(corners / played, 2) if played else 0,
        "avg_yellow_cards": round(yellow_cards / played, 2) if played else 0,
        "avg_red_cards": round(red_cards / played, 2) if played else 0,
    }


def get_standings(league_id, season):
    """
    Obtiene clasificación desde API-Football v3
    Endpoint: /standings?league={id}&season={year}
    """
    if not league_id or not season:
        return None

    data = api_get(
        "standings",
        params={"league": league_id, "season": season},
        cache_key=f"standings_{league_id}_{season}",
        ttl=3600
    )

    if not data or not isinstance(data, dict):
        return None

    response = data.get("response", [])
    if not response:
        return None

    standings_data = response[0] if isinstance(response, list) else response
    standings_list = standings_data.get("league", {}).get("standings", [[]])

    all_teams = []
    for group in standings_list:
        if isinstance(group, list):
            all_teams.extend(group)

    return all_teams


def find_team_in_standings(standings, team_id):
    """Busca un equipo en la clasificación por ID"""
    if not standings or not team_id:
        return None

    for team_data in standings:
        if team_data.get("team", {}).get("id") == team_id:
            all_stats = team_data.get("all", {})
            goals = all_stats.get("goals", {})
            return {
                "position": team_data.get("rank", 0),
                "playedGames": all_stats.get("played", 0),
                "won": all_stats.get("win", 0),
                "draw": all_stats.get("draw", 0),
                "lost": all_stats.get("lose", 0),
                "goalsFor": goals.get("for", 0),
                "goalsAgainst": goals.get("against", 0),
                "points": team_data.get("points", 0),
                "form": team_data.get("form", "")
            }
    return None


def get_h2h(team1_id, team2_id, last=5):
    """
    Obtiene H2H desde API-Football v3
    Endpoint: /fixtures/headtohead?h2h={id}-{id}
    """
    if not team1_id or not team2_id:
        return [], {}

    data = api_get(
        "fixtures/headtohead",
        params={"h2h": f"{team1_id}-{team2_id}", "last": last},
        cache_key=f"h2h_{team1_id}_{team2_id}",
        ttl=3600
    )

    if not data or not isinstance(data, dict):
        return [], {}

    fixtures = data.get("response", [])
    if not fixtures:
        return [], {}

    matches = []
    home_wins = away_wins = draws = 0
    home_goals = away_goals = 0

    for f in fixtures:
        teams = f.get("teams", {})
        goals = f.get("goals", {})

        home_team = teams.get("home", {})
        away_team = teams.get("away", {})

        hg = goals.get("home")
        ag = goals.get("away")

        matches.append({
            "date": f.get("fixture", {}).get("date", "")[:10],
            "home": home_team.get("name", ""),
            "away": away_team.get("name", ""),
            "homeScore": hg,
            "awayScore": ag,
            "competition": f.get("league", {}).get("name", "")
        })

        if hg is not None and ag is not None:
            home_goals += hg
            away_goals += ag
            if hg > ag:
                home_wins += 1
            elif hg == ag:
                draws += 1
            else:
                away_wins += 1

    stats = {
        "home_wins": home_wins,
        "away_wins": away_wins,
        "draws": draws,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "total_matches": len(fixtures)
    }

    return matches, stats


def get_predictions(fixture_id):
    """
    Obtiene predicciones desde API-Football v3
    Endpoint: /predictions?fixture={id}
    """
    if not fixture_id:
        return None

    data = api_get(
        "predictions",
        params={"fixture": fixture_id},
        cache_key=f"predictions_{fixture_id}",
        ttl=1800
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


def get_fixture_statistics(fixture_id):
    """
    Obtiene estadísticas de un partido específico desde API-Football v3
    Endpoint: /fixtures/statistics?fixture={id}
    Devuelve corners, tarjetas, posesión, tiros, etc.
    """
    if not fixture_id:
        return None

    data = api_get(
        "fixtures/statistics",
        params={"fixture": fixture_id},
        cache_key=f"fixture_stats_{fixture_id}",
        ttl=600
    )

    if not data or not isinstance(data, dict):
        return None

    response = data.get("response", [])
    if not response:
        return None

    # La respuesta tiene dos elementos: [home_stats, away_stats]
    home_stats = {}
    away_stats = {}

    for team_stats in response:
        team = team_stats.get("team", {})
        stats = team_stats.get("statistics", [])

        team_id = team.get("id")
        parsed = {}

        for stat in stats:
            stat_type = stat.get("type", "").lower().replace(" ", "_")
            value = stat.get("value")
            parsed[stat_type] = value

        if team_id:
            # Determinar si es local o visitante comparando con los IDs conocidos
            # Por ahora guardamos por team_id
            if not home_stats:
                home_stats = parsed
            else:
                away_stats = parsed

    return {
        "home": home_stats,
        "away": away_stats
    }


def get_fixtures_by_date(date, league_id=None, season=None):
    """
    Obtiene partidos por fecha desde API-Football v3
    Endpoint: /fixtures?date={YYYY-MM-DD}&league={id}&season={year}
    """
    params = {"date": date}
    if league_id:
        params["league"] = league_id
    if season:
        params["season"] = season

    data = api_get(
        "fixtures",
        params=params,
        cache_key=f"fixtures_{date}_{league_id or 'all'}",
        ttl=600
    )

    if not data or not isinstance(data, dict):
        return []

    return data.get("response", [])


def format_fixture(f):
    """Formatea un fixture de API-Football al formato del frontend"""
    fixture = f.get("fixture", {})
    teams = f.get("teams", {})
    goals = f.get("goals", {})
    league = f.get("league", {})

    home = teams.get("home", {})
    away = teams.get("away", {})

    status = fixture.get("status", {}).get("short", "NS")
    status_map = {
        "NS": "NS",
        "1H": "1H",
        "HT": "HT",
        "2H": "2H",
        "ET": "ET",
        "P": "PEN",
        "FT": "FT",
        "AET": "AET",
        "PEN": "PEN",
        "SUSP": "SUSP",
        "INT": "INT",
        "PST": "PST",
        "CANC": "CANC",
        "ABD": "ABD",
        "AWD": "AWD",
        "WO": "WO"
    }

    # matchday puede ser string (ej: "Regular Season - 36") o número
    raw_matchday = league.get("round", "")
    matchday = 0
    if isinstance(raw_matchday, int):
        matchday = raw_matchday
    elif isinstance(raw_matchday, str):
        # Extraer número de string como "Regular Season - 36"
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
        date = datetime.utcnow().strftime("%Y-%m-%d")

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
    matchday: str = Query("0"),  # CAMBIADO A STR para aceptar "Regular Season - 36"
    status: str = Query("SCHEDULED")
):
    logger.info(f"=== ANALYZE match_id={match_id}, home={home_team}({home_id}), away={away_team}({away_id}) ===")

    # === DETERMINAR LEAGUE ID Y SEASON ===
    comp_code = None
    for code, name in COMPETITIONS.items():
        if name.lower() in (league or "").lower():
            comp_code = code
            break

    # Si no encontramos por nombre, buscar por ID de competición
    if not comp_code:
        for code, lid in LEAGUE_IDS.items():
            if lid == competition_id:
                comp_code = code
                break

    league_id = get_league_id(comp_code) if comp_code else competition_id
    season = get_season()

    logger.info(f"Comp: {comp_code}, League ID: {league_id}, Season: {season}")

    # === ESTADÍSTICAS DE EQUIPOS ===
    home_stats = get_team_stats(home_id, league_id, season) if league_id else None
    away_stats = get_team_stats(away_id, league_id, season) if league_id else None

    home_mode = "API_FOOTBALL" if (home_stats and home_stats["played"] > 0) else "NO_DATA"
    away_mode = "API_FOOTBALL" if (away_stats and away_stats["played"] > 0) else "NO_DATA"

    # === STANDINGS ===
    standings = get_standings(league_id, season) if league_id else None

    home_table = find_team_in_standings(standings, home_id) if standings else None
    away_table = find_team_in_standings(standings, away_id) if standings else None

    if not home_table:
        home_table = {"position": 0, "points": 0, "won": 0, "draw": 0, "lost": 0, "goalsFor": 0, "goalsAgainst": 0}
    if not away_table:
        away_table = {"position": 0, "points": 0, "won": 0, "draw": 0, "lost": 0, "goalsFor": 0, "goalsAgainst": 0}

    # === FALLBACK A STANDINGS SI NO HAY STATS ===
    if not home_stats or home_stats["played"] == 0:
        home_stats = {
            "played": home_table.get("playedGames", 0),
            "won": home_table.get("won", 0),
            "draw": home_table.get("draw", 0),
            "lost": home_table.get("lost", 0),
            "goals_for": home_table.get("goalsFor", 0),
            "goals_against": home_table.get("goalsAgainst", 0),
            "avg_total_goals": round((home_table.get("goalsFor", 0) + home_table.get("goalsAgainst", 0)) / max(home_table.get("playedGames", 1), 1), 2),
            "avg_team_goals": round(home_table.get("goalsFor", 0) / max(home_table.get("playedGames", 1), 1), 2),
            "avg_conceded": round(home_table.get("goalsAgainst", 0) / max(home_table.get("playedGames", 1), 1), 2),
            "btts_pct": 0, "over_1_5_pct": 0, "over_2_5_pct": 0, "over_3_5_pct": 0,
            "clean_sheet_pct": 0, "failed_to_score_pct": 0,
            "form_string": home_table.get("form", ""),
            "form": [],
            "corners_total": 0,
            "yellow_cards": 0,
            "red_cards": 0,
            "avg_corners": 0,
            "avg_yellow_cards": 0,
            "avg_red_cards": 0,
        }
        home_mode = "STANDINGS_FALLBACK"

    if not away_stats or away_stats["played"] == 0:
        away_stats = {
            "played": away_table.get("playedGames", 0),
            "won": away_table.get("won", 0),
            "draw": away_table.get("draw", 0),
            "lost": away_table.get("lost", 0),
            "goals_for": away_table.get("goalsFor", 0),
            "goals_against": away_table.get("goalsAgainst", 0),
            "avg_total_goals": round((away_table.get("goalsFor", 0) + away_table.get("goalsAgainst", 0)) / max(away_table.get("playedGames", 1), 1), 2),
            "avg_team_goals": round(away_table.get("goalsFor", 0) / max(away_table.get("playedGames", 1), 1), 2),
            "avg_conceded": round(away_table.get("goalsAgainst", 0) / max(away_table.get("playedGames", 1), 1), 2),
            "btts_pct": 0, "over_1_5_pct": 0, "over_2_5_pct": 0, "over_3_5_pct": 0,
            "clean_sheet_pct": 0, "failed_to_score_pct": 0,
            "form_string": away_table.get("form", ""),
            "form": [],
            "corners_total": 0,
            "yellow_cards": 0,
            "red_cards": 0,
            "avg_corners": 0,
            "avg_yellow_cards": 0,
            "avg_red_cards": 0,
        }
        away_mode = "STANDINGS_FALLBACK"

    # === H2H ===
    h2h_matches, h2h_stats = get_h2h(home_id, away_id, last=5)

    # === PREDICCIONES ===
    predictions = get_predictions(match_id)

    # === ESTADÍSTICAS DEL PARTIDO (Corners, Tarjetas, etc.) ===
    fixture_stats = get_fixture_statistics(match_id)

    # === PROBABILIDADES ===
    probabilities = {
        "over_1_5": round((home_stats["over_1_5_pct"] + away_stats["over_1_5_pct"]) / 2, 1) if home_stats["played"] and away_stats["played"] else 0.0,
        "over_2_5": round((home_stats["over_2_5_pct"] + away_stats["over_2_5_pct"]) / 2, 1) if home_stats["played"] and away_stats["played"] else 0.0,
        "over_3_5": round((home_stats["over_3_5_pct"] + away_stats["over_3_5_pct"]) / 2, 1) if home_stats["played"] and away_stats["played"] else 0.0,
        "btts": round((home_stats["btts_pct"] + away_stats["btts_pct"]) / 2, 1) if home_stats["played"] and away_stats["played"] else 0.0,
        "total_expected_goals": round(home_stats["avg_team_goals"] + away_stats["avg_team_goals"], 2) if home_stats["played"] and away_stats["played"] else 0,
        "home_xg": 0,
        "away_xg": 0
    }

    # Odds desde predicciones
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
        "home_form": home_stats["form"],
        "away_form": away_stats["form"],
        "home_stats": home_stats,
        "away_stats": away_stats,
        "table_stats": {
            "home": home_table,
            "away": away_table
        },
        "h2h": {
            "matches": h2h_matches,
            "stats": h2h_stats
        },
        "predictions": predictions,
        "probabilities": probabilities,
        "odds": odds,
        "fixture_statistics": fixture_stats,
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
        "version": "9.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
