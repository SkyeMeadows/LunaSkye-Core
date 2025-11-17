from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

# Root Paths
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_PATH = PROJECT_ROOT / ".env"
LOGS_DIR = PROJECT_ROOT / "logs"
MODULES_DIR = PROJECT_ROOT / "modules"

# Subdirectories (modules)
DISCORD_DIR = MODULES_DIR / "discord"
ESI_DIR = MODULES_DIR / "esi"
WEBAPPS_DIR = MODULES_DIR / "webapps"

# Subdirectories (data)


# Subdirectories (logs)


# Subdirectories (webapps)
ANOM_PARSER_DIR = WEBAPPS_DIR / "anom_parser"
FIT_IMPORT_CALC_DIR = WEBAPPS_DIR / "fit_import_calc"