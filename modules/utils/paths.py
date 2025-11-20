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


# Subdirectories (webapps)
ANOM_PARSER_DIR = WEBAPPS_DIR / "anom_parser"
FIT_IMPORT_CALC_DIR = WEBAPPS_DIR / "fit_import_calc"

# Subdirectories (temp)
GRAPHS_TEMP_DIR = TEMP_DIR / "graphs"

# Subdirectories (market)
GRAPH_GENERATOR = MARKET_DIR / "graph_generator.py"

# Files (Data)
ITEM_IDS_FILE = DATA_DIR / "Item_IDs.csv"
ID_QUERY_LIST = DATA_DIR / "query_list.json"



# Ensure everything exists
for d in [DATA_DIR, TEMP_DIR, LOGS_DIR, MODULES_DIR]:
    d.mkdir(parents=True, exist_ok=True)