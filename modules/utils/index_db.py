import sqlite3
import asyncio
from modules.utils.paths import MARKET_DB_FILE_GSF, MARKET_DB_FILE_JITA

async def index_db(DB_PATH):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_orders_type_timestamp_price
            ON market_orders(type_id, timestamp DESC, price ASC);
        """)
        conn.commit()

async def main():
    #print("Indexing GSF DB...")
    #await index_db(MARKET_DB_FILE_GSF)
    print("Indexing Jita DB...")
    await index_db(MARKET_DB_FILE_JITA)
    print("Complete!")

asyncio.run(main())