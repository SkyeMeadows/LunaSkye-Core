import argparse
import asyncio
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from datetime import datetime, timedelta, UTC, timezone
from dotenv import load_dotenv
import aiosqlite
from collections import defaultdict
import sys
from pathlib import Path
import json

if __name__ == "__main__":
    # Dynamically add project root to sys.path
    project_root = Path(__file__).resolve().parent.parent.parent  # graph_generator.py → market → modules → root
    sys.path.insert(0, str(project_root))

from modules.utils.logging_setup import get_logger
from modules.utils.paths import GRAPHS_TEMP_DIR, ITEM_IDS_FILE, MARKET_DB_FILE_JITA, MARKET_DB_FILE_GSF, ORE_LIST

log = get_logger("GraphGenerator")

mpl.set_loglevel("warning")

# === Parse CLI arguments ===
log.debug("Parsing Arguments")
parser = argparse.ArgumentParser(description="Generate market graph for a specific item.")
parser.add_argument("--type_id", type=int, required=True)
parser.add_argument("--days", type=float, default=1, help="Number of days of data to include")
parser.add_argument("--market", type=str, default="jita", help="Market to pull data from")
args = parser.parse_args()



# === Load item names and IDs ===
items_df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")

async def connect_to_db(type_id: int, days: int, market: str):
    if market == "jita":
        MARKET_DB = MARKET_DB_FILE_JITA
    if market == "gsf":
        MARKET_DB = MARKET_DB_FILE_GSF
    else:
        log.error(f"Market {market} not recognized, defaulting to Jita")
        MARKET_DB = MARKET_DB_FILE_JITA
        log.debug(f"Market file located at {MARKET_DB}")

    async with aiosqlite.connect(MARKET_DB) as db:
        db.row_factory = aiosqlite.Row

        query = """
            SELECT timestamp, type_id, price, is_buy_order
            FROM market_orders
            WHERE type_id = ?
            AND is_buy_order = FALSE
        """
        params = [type_id]

        if days:
            cutoff = int((datetime.now(UTC) - timedelta(days=days)).timestamp())
            query += " AND timestamp >= ?"
            params.append(cutoff)

        query += " ORDER BY timestamp ASC"

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return rows

async def match_item_name(type_id: int):
    matched_row = items_df[items_df["typeID"] == type_id]
    if not matched_row.empty:
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {type_id} not found in type_ids.csv")
        return f"Unknown Item {type_id}"

async def generate_graph(type_id, days, market, type_name):
    sell_by_time = defaultdict(lambda: float('inf'))  # lowest sell wins


    rows = await connect_to_db(type_id, days, market)

    for row in rows:
        iso_ts = row["timestamp"]
        ts = pd.to_datetime(iso_ts)
        unix_timestamp = int(ts.timestamp())
        sell_by_time[unix_timestamp] = min(sell_by_time[unix_timestamp], row["price"])

    sell_times   = sorted(sell_by_time.keys())
    sell_prices  = [sell_by_time[t] for t in sell_times]

    sell_dt = [datetime.fromtimestamp(t, tz=timezone.utc) for t in sell_times]

    fig, (ax1) = plt.subplots(1, 1, figsize=(16,10), sharex=True, constrained_layout=True)
    ax1.plot(sell_dt, sell_prices, color="green", label=f"Sell Orders ({type_name})", linewidth=1, alpha=0.8)

    #Doing Averages
    if len(sell_prices) > 24:
        sell_ma = pd.Series(sell_prices).rolling(window=24, min_periods=1).mean()
        ax1.plot(sell_times, sell_ma, color="orange", linewidth=1, alpha=0.8, label="24h Sell Average")
    
    ax1.set_title(f"{market} chart for {type_name} - Past {days} days")
    ax1.set_ylabel("Price (ISK)")
    ax1.legend()

    os.makedirs(GRAPHS_TEMP_DIR, exist_ok=True)

    filepath =f"{GRAPHS_TEMP_DIR}/{market}_market_{type_name}_past_{days}d.png"

    plt.savefig(filepath, dpi=200, bbox_inches='tight')
    log.info(f"Saved figure to {filepath}")

    return filepath



        


async def main():
    type_id = args.type_id
    days = args.days if args.days > 0 else 1
    market = (args.market).lower()
    type_name = await match_item_name(type_id)

    filepath = await generate_graph(type_id, days, market, type_name)

    print(str(filepath))
    return 0

if __name__ == "__main__":
    asyncio.run(main())