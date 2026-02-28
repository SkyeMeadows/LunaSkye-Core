import argparse
import pandas as pd
from pathlib import Path
import sys
import asyncio
from collections import defaultdict
from datetime import datetime, timezone

if __name__ == "__main__":
    # Dynamically add project root to sys.path so local modules can be imported
    project_root = Path(__file__).resolve().parent.parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from modules.market.market_utils import get_market_db
from modules.utils.logging_setup import get_logger
from modules.esi.data_control import query_db_days, lowest_price_per_day
from modules.utils.paths import MARKET_DB_FILE_JITA, MARKET_DB_FILE_GSF, ITEM_IDS_FILE, MARKET_DB_FILE_PLEX

log = get_logger("MarketSummaryGenerator")

items_df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")

async def match_item_name(type_id: int):
    matched_row = items_df[items_df["typeID"] == type_id]
    if not matched_row.empty:
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {type_id} not found in type_ids.csv")
        return f"Unknown Item {type_id}"
    

async def create_summary(type_id: int, days: int, market: str, type_name: str):
    try:
        MARKET_DB = get_market_db(market)
    except ValueError as e:
        log.error("Error determining market database for '%s': %s. Defaulting to Jita.", market, e)
        MARKET_DB = MARKET_DB_FILE_JITA

    sell_by_time = defaultdict(lambda: float('inf'))

    rows = await lowest_price_per_day(type_id, MARKET_DB, days)

    if not rows:
        log.warning(f"No market data found for type ID {type_id} in market {market}")
        return "No data found!", 0, type_name

    start_price = rows[-1]['lowest_price']
    end_price = rows[0]['lowest_price']
    highest_price = float('-inf')
    lowest_price = float('inf')

    for row in rows:
        price = row['lowest_price']
        highest_price = max(highest_price, price)
        lowest_price = min(lowest_price, price)

    absolute_change = end_price - start_price
    percent_change = (absolute_change / start_price * 100)

    newest_date = datetime.strptime(rows[0]['order_date'], '%Y-%m-%d').date()
    oldest_date = datetime.strptime(rows[-1]['order_date'], '%Y-%m-%d').date()
    display_days = (newest_date - oldest_date).days

    summary = {
        "start_price": round(start_price, 2),
        "end_price": round(end_price, 2),
        "highest_price": round(highest_price, 2),
        "lowest_price": round(lowest_price, 2),
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