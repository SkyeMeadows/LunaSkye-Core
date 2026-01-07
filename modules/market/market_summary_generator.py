import argparse
import pandas as pd
from pathlib import Path
import sys
import asyncio
from collections import defaultdict

if __name__ == "__main__":
    # Dynamically add project root to sys.path
    project_root = Path(__file__).resolve().parent.parent.parent 
    sys.path.insert(0, str(project_root))

from modules.utils.logging_setup import get_logger
from modules.esi.data_control import query_db_days
from modules.utils.paths import MARKET_DB_FILE_JITA, MARKET_DB_FILE_GSF, ITEM_IDS_FILE

log = get_logger("MarketSummaryGenerator")

# === Parse CLI arguments ===
parser = argparse.ArgumentParser(description="Generate market graph for a specific item.")
parser.add_argument("--type_id", type=int, required=True)
parser.add_argument("--market", type=str, default="jita", required=True)
parser.add_argument("--days", type=float, default=1, required=False)
args = parser.parse_args()

items_df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")

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
    if market == "c-j6mt (gsf)":
        log.debug(f"Market recognized as C-J")
        MARKET_DB = MARKET_DB_FILE_GSF
        log.debug(f"Market file located at {MARKET_DB}")
    elif market != ("jita" or "c-j6mt (gsf)"):
        log.error(f"Market {market} not recognized, defaulting to Jita")
        MARKET_DB = MARKET_DB_FILE_JITA
        log.debug(f"Market file located at {MARKET_DB}")

    rows = await query_db_days(type_id, MARKET_DB, days)

    prices_by_timestamp = defaultdict(list)

    for row in rows:
        ts = row['timestamp']
        price = row['price']
        prices_by_timestamp[ts].append(price)

    timestamps = sorted(prices_by_timestamp.keys())

    oldest_ts = timestamps[0]
    start_price = min(prices_by_timestamp[oldest_ts])
    
    newest_ts = timestamps[-1]
    end_price = min(prices_by_timestamp[newest_ts])
    
    all_prices = [row['price'] for row in rows]
    sorted_prices = sorted(all_prices)
    n = len(sorted_prices)
    
    high_price = sorted_prices[int(n * 0.05)]
    low_index = max(0, int(n * 0.01))
    low_price = sorted_prices[low_index]
    
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
    ### for {type_name} in the past {days} days:
    Start Price: {summary['start_price']:,} ISK
    End Price: {summary['end_price']:,} ISK
    High Price: {summary['highest_price']:,} ISK
    Low Price: {summary['lowest_price']:,} ISK
    Change: {summary['absolute_change']:+,} ISK ({summary['change_percent']:+.2f}%)
    """

    return summary_text


async def main():
    type_id = args.type_id
    days = args.days if args.days > 0 else 1
    market = str((args.market).lower())
    log.debug(f"Market argument identified as: {market}")
    type_name = await match_item_name(type_id)

    summary = await create_summary(type_id, days, market, type_name)
    
    print(str(summary))
    return 0

if __name__ == "__main__":
    asyncio.run(main())