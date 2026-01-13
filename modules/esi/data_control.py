import aiosqlite
import pandas as pd
from modules.utils.logging_setup import get_logger
from modules.utils.paths import ITEM_IDS_VOLUME_FILE
from modules.utils.ore_controller import load_reprocess_ids

log = get_logger("DataControl")

async def save_orders(database_path, orders, fetched_time):
    rows_to_insert = []
    for order in orders:

        rows_to_insert.append((
            fetched_time,
            order["type_id"],
            order["volume_remain"],
            order["price"],
            order["is_buy_order"]
        ))

    async with aiosqlite.connect(database_path) as db:
        await db.executemany("""
            INSERT INTO market_orders (timestamp, type_id, volume_remain, price, is_buy_order)
            VALUES (?, ?, ?, ?, ?)
        """, rows_to_insert)
        await db.commit()
        await db.close()

async def pull_recent_data(type_id, market_db):

    async with aiosqlite.connect(market_db) as db:
        db.row_factory = aiosqlite.Row

        query = """
            SELECT timestamp, type_id, volume_remain, price, is_buy_order
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY type_id 
                        ORDER BY timestamp DESC, price ASC
                    ) AS rn
                FROM market_orders
                WHERE type_id = ?
                AND is_buy_order = FALSE
            )
            WHERE rn = 1
        """
    
        params = [type_id]

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            log.debug(f"Returning recent data for type id {type_id}: {rows}")
            return rows

async def save_ore_orders(database_path, ore_price, fetched_time, type_id):
    rows_to_insert = []

    rows_to_insert.append((
        fetched_time,
        type_id,
        0,
        ore_price,
        False
    ))

    async with aiosqlite.connect(database_path) as db:
        await db.executemany("""
            INSERT INTO market_orders (
                timestamp, 
                type_id, 
                volume_remain, 
                price, 
                is_buy_order
            )
            VALUES (?, ?, ?, ?, ?)
        """, rows_to_insert)
        await db.commit()
        await db.close()

async def query_db_days(type_id, market_db, days):

    async with aiosqlite.connect(market_db) as db:
        db.row_factory = aiosqlite.Row

        query = """
            SELECT 
                timestamp,
                price,
                volume_remain,
                is_buy_order
            FROM market_orders
            WHERE type_id = ?
                AND is_buy_order = FALSE
                AND timestamp >= datetime('now', '-' || ? || ' days')
            ORDER BY timestamp DESC, price DESC
        """
    
        params = [type_id, round(days*24)]

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            log.debug(f"Returning recent data for type id {type_id}")
            return rows
        
async def pull_fitting_price_data(type_id, market_db):
    query = """
        SELECT timestamp, type_id, volume_remain, price, is_buy_order
        FROM market_orders
        WHERE type_id = ?
          AND is_buy_order = 0
        ORDER BY timestamp DESC, price ASC
        LIMIT 1
    """

    async with aiosqlite.connect(market_db, timeout=15) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.commit()

        async with conn.execute(query, (type_id,)) as cursor:
            row = await cursor.fetchone()
            return row

async def get_volume(type_id):
    df = pd.read_csv(ITEM_IDS_VOLUME_FILE)
    result = df[df['typeID'] == type_id]['volume']
    return float(result.iloc[0])

async def save_mineral_price(database_path, orders, fetched_time):
    rows_to_insert = []
    reprocess_ids = await load_reprocess_ids()
    log.debug(f"Loaded reprocess_ids as {reprocess_ids}")
    for order in orders:
        type_id = order["type_id"]
        if type_id in reprocess_ids:
            log.debug(f"ID {type_id} is a reprocessed material, handling as such.")
            rows_to_insert.append((
                fetched_time,
                type_id,
                order["price"]
            ))

    async with aiosqlite.connect(database_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mineral_prices (
                timestamp INTEGER NOT NULL,
                type_id INTEGER NOT NULL,
                price REAL NOT NULL
            )
        """)
        await db.executemany("""
            INSERT INTO mineral_prices (
                timestamp,
                type_id, 
                price
            )
            VALUES (?, ?, ?)
        """, rows_to_insert)
        await db.commit()
        await db.close()
            
async def clear_mineral_table(database_path):
    async with aiosqlite.connect(database_path) as db:
        await db.execute("""
        DELETE FROM mineral_prices;
        """)
        await db.commit()
        await db.close()