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
from modules.utils.paths import TYPE_DICT, DB_DSN

log = get_logger("PriceChecker")

items_df = pd.read_csv(TYPE_DICT)

async def match_item_name(type_id: int):
    matched_row = items_df[items_df["typeID"] == type_id]
    if not matched_row.empty:
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {type_id} not found in type_ids.csv")
        return f"Unknown Item {type_id}"

async def price_check(type_id: int, market: str, type_name: str, pool: asyncpg.Pool):
    if market == "Jita":
        schema = "jita"
    elif market == "C-J6MT (GSF)":
        schema = "gsf"
    elif market == "PLEX":
        schema = "plex"
    else:
        log.error(f"Market {market} not recognized, defaulting to Jita")
        schema = "jita"

    price = await query_recent_price(type_id, pool, schema)
    return price
