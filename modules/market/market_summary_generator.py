import argparse
import asyncpg
import pandas as pd
from pathlib import Path
import sys
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from dotenv import load_dotenv

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from modules.market.market_utils import get_market_schema
from modules.utils.logging_setup import get_logger
from modules.esi.data_control import lowest_price_per_day
from modules.utils.paths import ITEM_IDS_FILE, DB_DSN

log = get_logger("MarketSummaryGenerator")

items_df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")

async def match_item_name(type_id: int):
    matched_row = items_df[items_df["typeID"] == type_id]
    if not matched_row.empty:
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {type_id} not found in type_ids.csv")
        return f"Unknown Item {type_id}"


async def create_summary(type_id: int, days: int, market: str, type_name: str, pool: asyncpg.Pool):
    try:
        schema = get_market_schema(market)
    except ValueError as e:
        log.error("Error determining market schema for '%s': %s. Defaulting to Jita.", market, e)
        schema = "jita"

    rows = await lowest_price_per_day(type_id, pool, schema, days)

    if not rows:
        log.warning(f"No market data found for type ID {type_id} in market {market}")
        return "No data found!", 0, type_name

    start_price = rows[-1]['lowest_price']
    end_price   = rows[0]['lowest_price']
    highest_price = float('-inf')
    lowest_price  = float('inf')

    for row in rows:
        price = row['lowest_price']
        highest_price = max(highest_price, price)
        lowest_price  = min(lowest_price, price)

    absolute_change = end_price - start_price
    percent_change  = (absolute_change / start_price * 100)

    # asyncpg returns DATE columns as Python date objects, not strings
    newest_date = rows[0]['order_date']
    oldest_date = rows[-1]['order_date']
    display_days = (newest_date - oldest_date).days

    summary = {
        "start_price":     round(start_price, 2),
        "end_price":       round(end_price, 2),
        "highest_price":   round(highest_price, 2),
        "lowest_price":    round(lowest_price, 2),
        "absolute_change": round(absolute_change, 2),
        "change_percent":  round(percent_change, 2),
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
    load_dotenv()
    type_id   = args.type_id
    days      = args.days if args.days > 0 else 1
    market    = str(args.market).lower()
    type_name = await match_item_name(type_id)

    pool = await asyncpg.create_pool(DB_DSN)
    summary, display_days, type_name = await create_summary(type_id, days, market, type_name, pool)
    await pool.close()

    print(str(summary))
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate market summary for a specific item.")
    parser.add_argument("--type_id", type=int, required=True)
    parser.add_argument("--market", type=str, default="jita", required=True)
    parser.add_argument("--days", type=int, default=1, required=False)
    args = parser.parse_args()

    asyncio.run(main())
