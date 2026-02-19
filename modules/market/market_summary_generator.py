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
from modules.esi.data_control import query_db_days
from modules.utils.paths import MARKET_DB_FILE_JITA, MARKET_DB_FILE_GSF, TYPE_DICTIONARY_FILE, MARKET_DB_FILE_PLEX

log = get_logger("MarketSummaryGenerator")

items_df = pd.read_csv(TYPE_DICTIONARY_FILE).drop_duplicates(subset="typeID")

async def match_item_name(type_id: int):
    matched_row = items_df[items_df["typeID"] == type_id]
    if not matched_row.empty:
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {type_id} not found in type_ids.csv")
        return f"Unknown Item {type_id}"
    

async def create_summary(type_id: int, days: int, market: str, type_name: str):
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

    sell_by_time = defaultdict(lambda: float('inf'))

    rows = await query_db_days(type_id, MARKET_DB, days)

    for row in rows:
        iso_ts = row["timestamp"]
        ts = pd.to_datetime(iso_ts)
        unix_timestamp = int(ts.timestamp())
        sell_by_time[unix_timestamp] = min(sell_by_time[unix_timestamp], row["price"])

    sell_times   = sorted(sell_by_time.keys())
    sell_prices  = [sell_by_time[t] for t in sell_times]

    sell_dt = [datetime.fromtimestamp(t, tz=timezone.utc) for t in sell_times]

    dt_price_pairs = list(zip(sell_dt, sell_prices))
    dt_price_pairs.sort(key=lambda pair: pair[0])

    sorted_dt, sorted_prices = zip(*dt_price_pairs)

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

    num_entries_back = days * 24
    index = max(-len(sell_times), -num_entries_back)

    oldest_ts = sell_times[index]
    start_price = sell_by_time[oldest_ts]
    
    newest_ts = sell_times[-1]
    end_price = sell_by_time[newest_ts]
    
    recent_prices = {ts: prices for ts, prices in sell_by_time.items() if ts >= oldest_ts} 
    sorted_timestamps = sorted(recent_prices.keys())
    sorted_prices = [recent_prices[ts] for ts in sorted_timestamps]
    n = len(sorted_prices)

    sorted_prices_by_value = sorted(sorted_prices)
    
    high_index = max(0, int(n * 0.95))
    high_price = sorted_prices_by_value[high_index]

    low_index = max(0, int(n * 0.05))
    low_price = sorted_prices_by_value[low_index]
    
    absolute_change = end_price - start_price
    percent_change = (absolute_change / start_price * 100) if start_price else 0

    summary = {
        "start_price": round(start_price, 2),
        "end_price": round(end_price, 2),
        "highest_price": round(high_price, 2),
        "lowest_price": round(low_price, 2),
        "absolute_change": round(absolute_change, 2),
        "change_percent": round(percent_change, 2)
    }

    summary_text = f"""
    ## {market.upper()} Price Summary
    ### for {type_name} in the past {display_days} days:
    Start Price: {summary['start_price']:,} ISK
    End Price: {summary['end_price']:,} ISK
    High Price: {summary['highest_price']:,} ISK
    Low Price: {summary['lowest_price']:,} ISK
    Change: {summary['absolute_change']:+,} ISK ({summary['change_percent']:+.2f}%)
    """

    return summary_text, display_days, type_name


async def main():
    type_id = args.type_id
    days = args.days if args.days > 0 else 1
    market = str((args.market).lower())
    log.debug(f"Market argument identified as: {market}")
    type_name = await match_item_name(type_id)

    summary, display_days, type_name = await create_summary(type_id, days, market, type_name)
    
    print(str(summary))
    return 0

if __name__ == "__main__":
    # === Parse CLI arguments ===
    parser = argparse.ArgumentParser(description="Generate market graph for a specific item.")
    parser.add_argument("--type_id", type=int, required=True)
    parser.add_argument("--market", type=str, default="jita", required=True)
    parser.add_argument("--days", type=int, default=1, required=False)
    args = parser.parse_args()

    asyncio.run(main())