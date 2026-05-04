import sys
from pathlib import Path

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))

market_schemas = {
    "jita": "jita",
    "c-j6mt (gsf)": "gsf",
    "plex": "plex",
}

def get_market_schema(market: str) -> str:
    if market in market_schemas:
        return market_schemas[market]
    else:
        raise ValueError(f"Market {market} not recognized. Valid options are: {', '.join(market_schemas.keys())}")
