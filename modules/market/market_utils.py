import sys
from pathlib import Path
from modules.utils.paths import MARKET_DB_FILE_JITA, MARKET_DB_FILE_GSF, MARKET_DB_FILE_PLEX

if __name__ == "__main__":
    # Dynamically add project root to sys.path
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))

market_files = {
    "jita": MARKET_DB_FILE_JITA,
    "c-j6mt (gsf)": MARKET_DB_FILE_GSF,
    "plex": MARKET_DB_FILE_PLEX
}

# Utility function to get the correct market database file based on the market name
# TODO: Replace market with an enum instead
def get_market_db(market: str) -> str:
    if market in market_files:
        return market_files[market]
    else:
        raise ValueError(f"Market {market} not recognized. Valid options are: {', '.join(market_files.keys())}")