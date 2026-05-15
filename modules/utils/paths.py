from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# ── Roots ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR    = PROJECT_ROOT / "data"
LOGS_DIR    = PROJECT_ROOT / "logs"
MODULES_DIR = PROJECT_ROOT / "modules"
TEMP_DIR    = PROJECT_ROOT / "temp"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# ── Modules ───────────────────────────────────────────────────────────────────

DB_DIR      = MODULES_DIR / "db"
DISCORD_DIR = MODULES_DIR / "discord"
ESI_DIR     = MODULES_DIR / "esi"
MARKET_DIR  = MODULES_DIR / "market"
UTILS_DIR   = MODULES_DIR / "utils"
WEBAPPS_DIR = MODULES_DIR / "webapps"

# ── Webapps ───────────────────────────────────────────────────────────────────

FIT_IMPORT_CALC_DIR    = WEBAPPS_DIR / "fitting_calculator"
INDUSTRY_DASHBOARD_DIR = WEBAPPS_DIR / "industry_dashboard"

# ── Temp ──────────────────────────────────────────────────────────────────────

GRAPHS_TEMP_DIR = TEMP_DIR / "graphs"

# ── Data files ────────────────────────────────────────────────────────────────

ITEM_IDS_FILE        = DATA_DIR / "Item_IDs.csv"
ITEM_IDS_VOLUME_FILE = DATA_DIR / "Item_IDs_volume.csv"
TYPE_DICT            = DATA_DIR / "TypeDictionary.csv"
ORE_LIST             = DATA_DIR / "ore_list.json"
ICE_PRODUCT_LIST     = DATA_DIR / "ice_product_list.json"
REPROCESS_YIELD      = DATA_DIR / "reprocess_yield.json"
REPROCESS_IDS        = DATA_DIR / "reprocess_item_ids.json"
REPACKAGED_VOLUME    = DATA_DIR / "repackaged_volumes.json"
ID_QUERY_LIST        = DATA_DIR / "query_list.json"

# ── ESI files ─────────────────────────────────────────────────────────────────

TOKEN_FILE         = ESI_DIR / "token.json"
RUNTIME_CACHE_PATH = ESI_DIR / "runtime_cache.txt"

# ── Environment ───────────────────────────────────────────────────────────────

DB_DSN     = os.getenv("DATABASE_URL")
CONFIG_PATH = PROJECT_ROOT / ".env"

# ── Bootstrap ─────────────────────────────────────────────────────────────────

for d in [DATA_DIR, TEMP_DIR, LOGS_DIR, GRAPHS_TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)
