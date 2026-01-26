import argparse
import pandas as pd
from pathlib import Path
import sys
import asyncio
from collections import defaultdict
from datetime import datetime, timezone

if __name__ == "__main__":
    # Dynamically add project root to sys.path
    project_root = Path(__file__).resolve().parent.parent.parent 
    sys.path.insert(0, str(project_root))

from modules.utils.logging_setup import get_logger
from modules.esi.data_control import query_recent_price
from modules.utils.paths import MARKET_DB_FILE_JITA, MARKET_DB_FILE_GSF, ITEM_IDS_FILE

log = get_logger("PriceChecker")

items_df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")

async def match_item_name(type_id: int):
    matched_row = items_df[items_df["typeID"] == type_id]
    if not matched_row.empty:
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {type_id} not found in type_ids.csv")
        return f"Unknown Item {type_id}"
    
async def price_check(type_id: int, market: str, type_name: str):
    if market == "jita":
        log.debug(f"Market recognized as Jita")
        MARKET_DB = MARKET_DB_FILE_JITA
        log.debug(f"Market file located at {MARKET_DB}")
    elif market == "c-j6mt (gsf)":
        log.debug(f"Market recognized as C-J")
        MARKET_DB = MARKET_DB_FILE_GSF
        log.debug(f"Market file located at {MARKET_DB}")
    else:
        log.error(f"Market {market} not recognized, defaulting to Jita")
        MARKET_DB = MARKET_DB_FILE_JITA
        log.debug(f"Market file located at {MARKET_DB}")
    
    rows = await query_recent_price(type_id, MARKET_DB)

    price = rows[3]

    return price

async def main():
    type_id = args.type_id
    market = str((args.market).lower())
    log.debug(f"Market argument identified as: {market}")
    type_name = await match_item_name(type_id)

    price = await price_check(type_id, market, type_name)

    price_text = f"The Current Price in {market} for {type_name} is **{price}**."

    print(str(price_text))
    return 0

if __name__ == "__main__":
    # === Parse CLI arguments ===
    parser = argparse.ArgumentParser(description="Generate market graph for a specific item.")
    parser.add_argument("--type_id", type=int, required=True)
    parser.add_argument("--market", type=str, default="jita", required=True)
    args = parser.parse_args()

    asyncio.run(main())