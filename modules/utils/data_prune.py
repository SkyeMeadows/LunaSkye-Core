import aiosqlite
from datetime import datetime, timedelta, UTC
import os
import argparse
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from modules.utils.logging_setup import get_logger

log = get_logger("DataPrune")

load_dotenv()
PRUNE_AGE_DAYS = int(os.getenv("PRUNE_AGE_DAYS"))

parser = argparse.ArgumentParser()
parser.add_argument("--db_path", type=Path, required=True)
args = parser.parse_args()

db_path = args.db_path

async def prune_old_data(DB_FILE):

    cutoff = datetime.now(UTC) - timedelta(days=PRUNE_AGE_DAYS)
    cutoff_str = cutoff.isoformat()
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        
        command = """
            DELETE FROM market_orders
            WHERE timestamp < ?
            AND rowid IN (
                WITH numbered AS (
                    SELECT 
                        rowid,
                        ROW_NUMBER() OVER (
                            PARTITION BY type_id 
                            ORDER BY timestamp ASC
                        ) AS row_num
                    FROM market_orders
                    WHERE timestamp < ?
                )
            SELECT rowid
            FROM numbered
            WHERE row_num % 4 != 1
        )
        """

        params = [cutoff_str, cutoff_str]
        
        async with db.execute(command, tuple(params)) as cursor:
        
            deleted_count = cursor.rowcount
            log.info(f"Pruned {deleted_count} entries")
            
        await db.commit()
        await db.close()

async def main():
    await prune_old_data(db_path)

asyncio.run(main())
    

    