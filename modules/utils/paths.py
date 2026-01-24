from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Root Paths
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_PATH = PROJECT_ROOT / ".env"
LOGS_DIR = PROJECT_ROOT / "logs"
MODULES_DIR = PROJECT_ROOT / "modules"
TEMP_DIR = PROJECT_ROOT / "temp"

# Subdirectories (modules)
DISCORD_DIR = MODULES_DIR / "discord"
ESI_DIR = MODULES_DIR / "esi"
WEBAPPS_DIR = MODULES_DIR / "webapps"
UTILS_DIR = MODULES_DIR / "utils"
MARKET_DIR = MODULES_DIR / "market"

# Subdirectories (data)


# Subdirectories (logs)


# Subdirectories (utils)
ID_ICONS_DIR = UTILS_DIR / "images"


# Subdirectories (webapps)
ANOM_PARSER_DIR = WEBAPPS_DIR / "anom_parser"
FIT_IMPORT_CALC_DIR = WEBAPPS_DIR / "fit_import_calc"

# Subdirectories (temp)
GRAPHS_TEMP_DIR = TEMP_DIR / "graphs"

# Subdirectories (market)
GRAPH_GENERATOR = MARKET_DIR / "graph_generator.py"
MARKET_SUMMARY_GENERATOR = MARKET_DIR / "market_summary_generator.py"

# Files (Data)
ITEM_IDS_FILE = DATA_DIR / "Item_IDs.csv"
ID_QUERY_LIST = DATA_DIR / "query_list.json"
MARKET_DB_FILE_JITA = DATA_DIR / "jita_market_prices.db"
MARKET_DB_FILE_GSF = DATA_DIR / "gsf_market_prices.db"
ORE_LIST = DATA_DIR / "ore_list.json"
ICE_PRODUCT_LIST = DATA_DIR / "ice_product_list.json"
REPROCESS_YIELD = DATA_DIR / "reprocess_yield.json"
REPROCESS_IDS = DATA_DIR / "reprocess_item_ids.json"
ITEM_IDS_VOLUME_FILE = DATA_DIR / "Item_IDs_volume.csv"
REPACKAGED_VOLUME = DATA_DIR / "repackaged_volumes.json"

# Files (ESI)
TOKEN_FILE = ESI_DIR / "token.json"
AT_MANAGER_FILE = ESI_DIR / "at_manager.py"
RUNTIME_CACHE_PATH = ESI_DIR / "runtime_cache.txt"



# Ensure everything exists
for d in [DATA_DIR, TEMP_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)