import argparse
import asyncio
import asyncpg
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from datetime import datetime, timedelta, UTC, timezone
from dotenv import load_dotenv
from collections import defaultdict
import sys
from pathlib import Path
import matplotlib.dates as mdates

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))

from modules.utils.logging_setup import get_logger
from modules.utils.paths import GRAPHS_TEMP_DIR, ITEM_IDS_FILE, DB_DSN
from modules.market.market_utils import get_market_schema

log = get_logger("GraphGenerator")

mpl.set_loglevel("warning")

items_df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")

def format_price(value, pos):
    if value >= 1e9:
        return f'{value / 1e9:.1f}B'
    elif value >= 1e6:
        return f'{value / 1e6:.1f}M'
    else:
        return f'{value:,.0f}'

async def connect_to_db(type_id: int, days: int, market: str, pool: asyncpg.Pool):
    try:
        schema = get_market_schema(market)
    except ValueError:
        log.error(f"Market {market} not recognized, defaulting to Jita")
        schema = "jita"

    cutoff = datetime.now(UTC) - timedelta(days=days)

    query = f"""
        SELECT timestamp, type_id, price, is_buy_order
        FROM {schema}.market_orders
        WHERE type_id = $1
        AND is_buy_order = FALSE
        AND timestamp >= $2
        ORDER BY timestamp ASC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, type_id, cutoff)
        return rows

async def match_item_name(type_id: int):
    matched_row = items_df[items_df["typeID"] == type_id]
    if not matched_row.empty:
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {type_id} not found in type_ids.csv")
        return f"Unknown Item {type_id}"

async def generate_graph(type_id, days, market, type_name, pool: asyncpg.Pool):
    sell_by_time = defaultdict(lambda: float('inf'))

    rows = await connect_to_db(type_id, days, market, pool)

    for row in rows:
        ts = pd.to_datetime(row["timestamp"])
        unix_timestamp = int(ts.timestamp())
        sell_by_time[unix_timestamp] = min(sell_by_time[unix_timestamp], row["price"])

    sell_times  = sorted(sell_by_time.keys())
    sell_prices = [sell_by_time[t] for t in sell_times]
    sell_dt     = [datetime.fromtimestamp(t, tz=timezone.utc) for t in sell_times]

    if sell_dt:
        delta = sell_dt[-1] - sell_dt[0]
        actual_days = delta.total_seconds() / 86400
        display_days = round(min(days, actual_days), 1)
    else:
        display_days = 0

    if display_days == 0:
        return None, display_days, type_name

    plt.style.use("dark_background")
    fig, ax1 = plt.subplots(1, 1, figsize=(16, 10), sharex=True, constrained_layout=True)
    ax1.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(format_price))
    ax1.plot(sell_dt, sell_prices, color="green", linestyle='--', marker='o', label=f"Sell Orders ({type_name})", linewidth=1, alpha=0.8)
    ax1.margins(x=0)

    if actual_days > 1:
        df = pd.DataFrame({'price': sell_prices}, index=sell_dt)
        sell_ma = df['price'].rolling('24h', min_periods=1).mean()
        ax1.plot(df.index, sell_ma, color="orange", linestyle='-', linewidth=1, alpha=0.8, label="24h Sell Average")

    market_text = str(market).upper()
    ax1.set_title(f"{market_text} chart for {type_name} - Past {display_days} days")
    ax1.set_ylabel("Price (ISK)")
    ax1.set_xlabel("Time (UTC)")
    ax1.legend()
    ax1.grid(True, which='major', alpha=0.5)
    ax1.grid(True, which='minor', alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %H:%M'))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, int(days // 10))))
    plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')
    fig.autofmt_xdate()

    os.makedirs(GRAPHS_TEMP_DIR, exist_ok=True)
    filepath = f"{GRAPHS_TEMP_DIR}/{market}_market_{type_name}_past_{display_days}d.png"
    fig.savefig(filepath, dpi=200, bbox_inches='tight')
    log.info(f"Saved figure to {filepath}")

    return filepath, display_days, type_name


async def generate_combined_graph(type_id, days, type_name, pool: asyncpg.Pool):
    jita_rows = await connect_to_db(type_id, days, "jita", pool)
    log.debug(f"Got jita_rows, length is {len(jita_rows)}")
    gsf_rows  = await connect_to_db(type_id, days, "c-j6mt (gsf)", pool)
    log.debug(f"Got gsf_rows, length is {len(gsf_rows)}")

    jita_sell_by_time = defaultdict(lambda: float('inf'))
    gsf_sell_by_time  = defaultdict(lambda: float('inf'))

    for row in jita_rows:
        unix_timestamp = int(pd.to_datetime(row["timestamp"]).timestamp())
        jita_sell_by_time[unix_timestamp] = min(jita_sell_by_time[unix_timestamp], row["price"])

    for row in gsf_rows:
        unix_timestamp = int(pd.to_datetime(row["timestamp"]).timestamp())
        gsf_sell_by_time[unix_timestamp] = min(gsf_sell_by_time[unix_timestamp], row["price"])

    jita_sell_times  = sorted(jita_sell_by_time.keys())
    jita_sell_prices = [jita_sell_by_time[t] for t in jita_sell_times]
    gsf_sell_times   = sorted(gsf_sell_by_time.keys())
    gsf_sell_prices  = [gsf_sell_by_time[t] for t in gsf_sell_times]

    jita_sell_dt = [datetime.fromtimestamp(t, tz=timezone.utc) for t in jita_sell_times]
    gsf_sell_dt  = [datetime.fromtimestamp(t, tz=timezone.utc) for t in gsf_sell_times]

    jita_display_days = round(min(days, (jita_sell_dt[-1] - jita_sell_dt[0]).total_seconds() / 86400), 1) if jita_sell_dt else 0
    gsf_display_days  = round(min(days, (gsf_sell_dt[-1]  - gsf_sell_dt[0]).total_seconds()  / 86400), 1) if gsf_sell_dt  else 0
    true_display_days = min(jita_display_days, gsf_display_days)

    if true_display_days == 0:
        return None, true_display_days, type_name

    plt.style.use("dark_background")
    fig, ax = plt.subplots(1, 1, figsize=(16, 10), sharex=True, sharey=True, constrained_layout=True)
    ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(format_price))
    ax.plot(jita_sell_dt, jita_sell_prices, color="Green", linestyle=' ', marker='o', label=f"Jita Sell Orders ({type_name})", linewidth=1, alpha=0.8)
    ax.plot(gsf_sell_dt,  gsf_sell_prices,  color="Yellow", linestyle=' ', marker='o', label=f"GSF Sell Orders ({type_name})",  linewidth=1, alpha=0.8)
    ax.margins(x=0)

    actual_days = max(jita_display_days, gsf_display_days)
    if actual_days > 1:
        df = pd.DataFrame({'price': jita_sell_prices}, index=jita_sell_dt)
        ax.plot(df.index, df['price'].rolling('24h', min_periods=1).mean(), color="Green",  linestyle='-', linewidth=1, alpha=0.8, label="Jita 24h Sell Average")
        df = pd.DataFrame({'price': gsf_sell_prices}, index=gsf_sell_dt)
        ax.plot(df.index, df['price'].rolling('24h', min_periods=1).mean(), color="Yellow", linestyle='-', linewidth=1, alpha=0.8, label="GSF 24h Sell Average")

    ax.set_title(f"Combined market chart for {type_name} - Past {true_display_days} days")
    ax.set_ylabel("Price (ISK)")
    ax.set_xlabel("Time (UTC)")
    ax.legend()
    ax.grid(True, which='major', alpha=0.5)
    ax.grid(True, which='minor', alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %H:%M'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, int(days // 10))))
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    fig.autofmt_xdate()

    os.makedirs(GRAPHS_TEMP_DIR, exist_ok=True)
    filepath = f"{GRAPHS_TEMP_DIR}/combined_market_{type_name}_past_{true_display_days}d.png"
    fig.savefig(filepath, dpi=200, bbox_inches='tight')
    log.info(f"Saved figure to {filepath}")

    return filepath, true_display_days, type_name


async def main():
    load_dotenv()
    type_id   = args.type_id
    days      = args.days if args.days > 0 else 1
    market    = str(args.market).lower()
    type_name = await match_item_name(type_id)

    pool = await asyncpg.create_pool(DB_DSN)

    filepath, display_days, type_name = await generate_graph(type_id, days, market, type_name, pool)
    print(str(filepath))

    filepath, display_days, type_name = await generate_combined_graph(type_id, days, type_name, pool)

    await pool.close()
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate market graph for a specific item.")
    parser.add_argument("--type_id", type=int, required=True)
    parser.add_argument("--market", type=str, default="jita", help="Market to pull data from")
    parser.add_argument("--days", type=float, default=1, help="Number of days of data to include")
    args = parser.parse_args()

    asyncio.run(main())
