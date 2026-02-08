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
import matplotlib.dates as mdates

if __name__ == "__main__":
    # Dynamically add project root to sys.path
    project_root = Path(__file__).resolve().parent.parent.parent  # graph_generator.py → market → modules → root
    sys.path.insert(0, str(project_root))

from modules.utils.logging_setup import get_logger
from modules.utils.paths import GRAPHS_TEMP_DIR, ITEM_IDS_FILE, MARKET_DB_FILE_JITA, MARKET_DB_FILE_GSF, MARKET_DB_FILE_PLEX

log = get_logger("GraphGenerator")

mpl.set_loglevel("warning")

# === Load item names and IDs ===
items_df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")

async def connect_to_db(type_id: int, days: int, market: str):
    if market == "jita":
        log.debug(f"Market recognized as Jita")
        MARKET_DB = MARKET_DB_FILE_JITA
        log.debug(f"Market file located at {MARKET_DB}")
    elif market == "c-j6mt (gsf)":
        log.debug(f"Market recognized as C-J")
        MARKET_DB = MARKET_DB_FILE_GSF
        log.debug(f"Market file located at {MARKET_DB}")
    elif market == "plex":
        log.debug(f"Market recognized as PLEX Market")
        MARKET_DB = MARKET_DB_FILE_PLEX
        log.debug(f"Market file located at {MARKET_DB}")
    else:
        log.error(f"Market {market} not recognized, defaulting to Jita")
        MARKET_DB = MARKET_DB_FILE_JITA
        log.debug(f"Market file located at {MARKET_DB}")

    async with aiosqlite.connect(MARKET_DB) as db:
        db.row_factory = aiosqlite.Row

        now_datetime = datetime.now(UTC)
        time_delta = timedelta(days=days)

        cutoff = (now_datetime - time_delta)
        cutoff_str = cutoff.isoformat()

        query = """
            SELECT timestamp, type_id, price, is_buy_order
            FROM market_orders
            WHERE type_id = ?
            AND is_buy_order = FALSE
            AND timestamp >= ?
            ORDER BY timestamp ASC
        """
        params = [type_id, cutoff_str]
        log.debug(f"Query set, params set as {params}")

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

    if sell_dt:
        oldest = sell_dt[0]
        most_recent = sell_dt[-1]
        delta = most_recent - oldest
        actual_days = delta.total_seconds() / 86400
        display_days = round(min(days, actual_days),1)
    else:
        display_days = 0

    if display_days == 0:
        return None, display_days, type_name

    plt.style.use("dark_background")

    fig, (ax1) = plt.subplots(1, 1, figsize=(16,10), sharex=True, constrained_layout=True)

    ax1.plot(sell_dt, sell_prices, color="green", linestyle='--', marker='o', label=f"Sell Orders ({type_name})", linewidth=1, alpha=0.8)

    ax1.margins(x=0)

    #Doing Averages
    if actual_days > 1:
        df = pd.DataFrame({'price': sell_prices}, index=sell_dt)
        sell_ma = df['price'].rolling('24h', min_periods=1).mean()
        ax1.plot(df.index, sell_ma, color="orange", linestyle='-', linewidth=1, alpha=0.8, label="24h Sell Average")
    
    ax1.set_title(f"{market} chart for {type_name} - Past {display_days} days")
    ax1.set_ylabel("Price (ISK)")
    ax1.set_xlabel("Time (UTC)")
    ax1.legend()

    ax1.grid(True, which='major', alpha=0.5)
    ax1.grid(True, which='minor', alpha=0.3)

    # === Date formatting ===
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %H:%M'))

    # Smart tick spacing based on time range
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, int(days // 10))))

    plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')
    fig.autofmt_xdate()  # helps with layout

    os.makedirs(GRAPHS_TEMP_DIR, exist_ok=True)

    filepath =f"{GRAPHS_TEMP_DIR}/{market}_market_{type_name}_past_{display_days}d.png"

    fig.savefig(filepath, dpi=200, bbox_inches='tight')
    log.info(f"Saved figure to {filepath}")

    return filepath, display_days, type_name



async def generate_combined_graph(type_id, days, type_name):
    jita_rows = await connect_to_db(type_id, days, "jita")
    log.debug(f"Got jita_rows, length is {len(jita_rows)}")

    gsf_rows = await connect_to_db(type_id, days, "c-j6mt (gsf)")
    log.debug(f"Got gsf_rows, length is {len(gsf_rows)}")

    jita_sell_by_time = defaultdict(lambda: float('inf'))  # lowest sell wins
    gsf_sell_by_time = defaultdict(lambda: float('inf'))  # lowest sell wins

    for row in jita_rows:
        iso_ts = row["timestamp"]
        ts = pd.to_datetime(iso_ts)
        unix_timestamp = int(ts.timestamp())
        jita_sell_by_time[unix_timestamp] = min(jita_sell_by_time[unix_timestamp], row["price"])

    for row in gsf_rows:
        iso_ts = row["timestamp"]
        ts = pd.to_datetime(iso_ts)
        unix_timestamp = int(ts.timestamp())
        gsf_sell_by_time[unix_timestamp] = min(gsf_sell_by_time[unix_timestamp], row["price"])

    jita_sell_times = sorted(jita_sell_by_time.keys())
    jita_sell_prices  = [jita_sell_by_time[t] for t in jita_sell_times]

    gsf_sell_times = sorted(gsf_sell_by_time.keys())
    gsf_sell_prices  = [gsf_sell_by_time[t] for t in gsf_sell_times]

    jita_sell_dt = [datetime.fromtimestamp(t, tz=timezone.utc) for t in jita_sell_times]
    gsf_sell_dt = [datetime.fromtimestamp(t, tz=timezone.utc) for t in gsf_sell_times]

    if jita_sell_dt:
        oldest = jita_sell_dt[0]
        most_recent = jita_sell_dt[-1]
        delta = most_recent - oldest
        actual_days = delta.total_seconds() / 86400
        jita_display_days = round(min(days, actual_days),1)
    else:
        jita_display_days = 0

    if gsf_sell_dt:
        oldest = gsf_sell_dt[0]
        most_recent = gsf_sell_dt[-1]
        delta = most_recent - oldest
        actual_days = delta.total_seconds() / 86400
        gsf_display_days = round(min(days, actual_days),1)
    else:
        gsf_display_days = 0

    true_display_days = min(jita_display_days, gsf_display_days)

    if true_display_days == 0:
        return None, true_display_days, type_name
    
    plt.style.use("dark_background")

    fig, ax = plt.subplots(1, 1, figsize=(16,10), sharex=True, sharey=True, constrained_layout=True)

    ax.plot(jita_sell_dt, jita_sell_prices, color="Green", linestyle=' ', marker='o', label=f"Jita Sell Orders ({type_name})", linewidth=1, alpha=0.8)

    ax.plot(gsf_sell_dt, gsf_sell_prices, color="Yellow", linestyle=' ', marker='o', label=f"GSF Sell Orders ({type_name})", linewidth=1, alpha=0.8)

    ax.margins(x=0)

    # Jita Averages
    if actual_days > 1:
        df = pd.DataFrame({'price': jita_sell_prices}, index=jita_sell_dt)
        sell_ma = df['price'].rolling('24h', min_periods=1).mean()
        ax.plot(df.index, sell_ma, color="Green", linestyle='-', linewidth=1, alpha=0.8, label="Jita 24h Sell Average")
    
    # GSF Averages
    if actual_days > 1:
        df = pd.DataFrame({'price': gsf_sell_prices}, index=gsf_sell_dt)
        sell_ma = df['price'].rolling('24h', min_periods=1).mean()
        ax.plot(df.index, sell_ma, color="Yellow", linestyle='-', linewidth=1, alpha=0.8, label="GSF 24h Sell Average")
    
    ax.set_title(f"Combined market chart for {type_name} - Past {true_display_days} days")
    ax.set_ylabel("Price (ISK)")
    ax.set_xlabel("Time (UTC)")
    ax.legend()

    ax.grid(True, which='major', alpha=0.5)
    ax.grid(True, which='minor', alpha=0.3)

    # === Date formatting ===
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %H:%M'))

    # Smart tick spacing based on time range
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, int(days // 10))))

    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    fig.autofmt_xdate()  # helps with layout

    os.makedirs(GRAPHS_TEMP_DIR, exist_ok=True)

    filepath =f"{GRAPHS_TEMP_DIR}/combined_market_{type_name}_past_{true_display_days}d.png"

    fig.savefig(filepath, dpi=200, bbox_inches='tight')
    log.info(f"Saved figure to {filepath}")

    return filepath, true_display_days, type_name



async def main():
    type_id = args.type_id
    days = args.days if args.days > 0 else 1
    market = str((args.market).lower())
    log.debug(f"Market argument identified as: {market}")
    type_name = await match_item_name(type_id)

    filepath, display_days, type_name = await generate_graph(type_id, days, market, type_name)
    print(str(filepath))

    log.debug(f"Next")
    filepath, display_days, type_name = await generate_combined_graph(type_id, days, type_name)
    return 0

if __name__ == "__main__":
    # === Parse CLI arguments ===
    log.debug("Parsing Arguments")
    parser = argparse.ArgumentParser(description="Generate market graph for a specific item.")
    parser.add_argument("--type_id", type=int, required=True)
    parser.add_argument("--market", type=str, default="jita", help="Market to pull data from")
    parser.add_argument("--days", type=float, default=1, help="Number of days of data to include")
    args = parser.parse_args()

    asyncio.run(main())