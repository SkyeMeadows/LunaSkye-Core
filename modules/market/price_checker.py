import argparse
import asyncpg
import pandas as pd
from pathlib import Path
import sys
import asyncio
from dotenv import load_dotenv

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))

from modules.utils.logging_setup import get_logger
from modules.esi.data_control import query_recent_price
from modules.utils.paths import ITEM_IDS_FILE, DB_DSN

log = get_logger("PriceChecker")

items_df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")

async def match_item_name(type_id: int):
    matched_row = items_df[items_df["typeID"] == type_id]
    if not matched_row.empty:
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {type_id} not found in type_ids.csv")
        return f"Unknown Item {type_id}"

async def price_check(type_id: int, market: str, type_name: str, pool: asyncpg.Pool):
    if market == "jita":
        schema = "jita"
    elif market == "c-j6mt (gsf)":
        schema = "gsf"
    else:
        log.error(f"Market {market} not recognized, defaulting to Jita")
        schema = "jita"

    row = await query_recent_price(type_id, pool, schema)
    price = row[3]
    return price

async def main():
    load_dotenv()
    type_id   = args.type_id
    market    = str(args.market).lower()
    type_name = await match_item_name(type_id)

    pool  = await asyncpg.create_pool(DB_DSN)
    price = await price_check(type_id, market, type_name, pool)
    await pool.close()

    print(f"The Current Price in {market} for {type_name} is **{price}**.")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check current price for a specific item.")
    parser.add_argument("--type_id", type=int, required=True)
    parser.add_argument("--market", type=str, default="jita", required=True)
    args = parser.parse_args()

    asyncio.run(main())
