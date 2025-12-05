import argparse
import asyncio
import os
from pickle import MARK
import time
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from datetime import datetime, timedelta
from matplotlib.dates import DayLocator, DateFormatter, HourLocator, AutoDateLocator
from matplotlib.ticker import MaxNLocator
import logging
from dotenv import load_dotenv
import aiosqlite
from collections import defaultdict
from modules.utils.logging_setup import get_logger
from modules.utils.paths import GRAPHS_TEMP_DIR, ITEM_IDS_FILE, DATA_DIR, MARKET_DB_FILE_JITA ,MARKET_DB_FILE_GSF


log = get_logger("GraphGenerator")

mpl.set_loglevel("warning")


# === Parse CLI arguments ===
log.debug("Parsing Arguments")
parser = argparse.ArgumentParser(description="Generate market graph for a specific item.")
parser.add_argument("--item_id", type=int, required=True)
parser.add_argument("--days", type=float, default=1, help="Number of days of data to include")
parser.add_argument("--market", type=str, default="jita", choices=["jita", "gsf"], help="Market to pull data from"))
args = parser.parse_args()
log.debug("Arguments Parsed")


# === Load item names and IDs ===
items_df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")

async def connect_to_db(item_id: int, days: int, market: str):
    if market == "jita":
        MARKET_DB = MARKET_DB_FILE_JITA
    if market == "gsf":
        MARKET_DB = MARKET_DB_FILE_GSF
    else:
        log.error(f"Market {market} not recognized, defaulting to Jita")
        MARKET_DB = MARKET_DB_FILE_JITA

    async with aiosqlite.connect(MARKET_DB) as db:
        db.row_factory = aiosqlite.Row

        query = """
            SELECT timestamp, item_ID, price
            FROM market_data
            WHERE item_id = ?
        """
        params = [item_id]

        if days:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            query += " AND timestamp >= ?"
            params.append(cutoff)

        query += " ORDER BY timestamp ASC"

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return rows

'''
async def match_item_name(item_id: int):
    matched_row = items_df[items_df["typeID"] == item_id]
    if not matched_row.empty:
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {item_id} not found in Item_IDs.csv")
        return f"Unknown Item {item_id}"
'''

async def generate_graph(item_id, days, market):
    rows = await connect_to_db(item_id, days, market)

    for row in rows:
        dt = datetime.fromisoformat(row["timestamp"])
        


async def main():
    item_id = args.item_id
    days = args.days if args.days > 0 else 1
    market = args.market
    #type_name = await match_item_name(item_id)

    await generate_graph(item_id, days, market)

if __name__ == "__main__":
    asyncio.run(main())