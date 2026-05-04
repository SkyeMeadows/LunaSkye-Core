import asyncpg
import pandas as pd
from modules.utils.logging_setup import get_logger
from modules.utils.paths import ITEM_IDS_VOLUME_FILE
from modules.utils.ore_controller import load_reprocess_ids

log = get_logger("DataControl")

async def save_orders(pool: asyncpg.Pool, schema: str, orders, fetched_time):
    rows_to_insert = [
        (fetched_time, order["type_id"], order["volume_remain"], order["price"], order["is_buy_order"])
        for order in orders
    ]
    async with pool.acquire() as conn:
        await conn.executemany(f"""
            INSERT INTO {schema}.market_orders (timestamp, type_id, volume_remain, price, is_buy_order)
            VALUES ($1, $2, $3, $4, $5)
        """, rows_to_insert)

async def pull_recent_data(type_id, pool: asyncpg.Pool, schema: str):
    query = f"""
        SELECT timestamp, type_id, volume_remain, price, is_buy_order
        FROM (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY type_id
                    ORDER BY timestamp DESC, price ASC
                ) AS rn
            FROM {schema}.market_orders
            WHERE type_id = $1
            AND is_buy_order = FALSE
        ) AS sub
        WHERE rn = 1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, type_id)
        log.debug(f"Returning recent data for type id {type_id}: {rows}")
        return rows

async def save_ore_orders(pool: asyncpg.Pool, schema: str, ore_price, fetched_time, type_id):
    async with pool.acquire() as conn:
        await conn.execute(f"""
            INSERT INTO {schema}.market_orders (timestamp, type_id, volume_remain, price, is_buy_order)
            VALUES ($1, $2, $3, $4, $5)
        """, fetched_time, type_id, 0, ore_price, False)

async def query_db_days(type_id, pool: asyncpg.Pool, schema: str, days):
    query = f"""
        SELECT timestamp, price, volume_remain, is_buy_order
        FROM {schema}.market_orders
        WHERE type_id = $1
            AND is_buy_order = FALSE
            AND timestamp >= NOW() - $2 * INTERVAL '1 hour'
        ORDER BY timestamp DESC, price DESC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, type_id, round(days * 24))
        log.debug(f"Returning recent data for type id {type_id}")
        return rows

async def lowest_price_per_day(type_id, pool: asyncpg.Pool, schema: str, days):
    query = f"""
        SELECT
            DATE(timestamp) AS order_date,
            MIN(price) AS lowest_price
        FROM {schema}.market_orders
        WHERE type_id = $1
            AND is_buy_order = FALSE
            AND timestamp >= NOW() - $2 * INTERVAL '1 hour'
        GROUP BY order_date
        ORDER BY order_date DESC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, type_id, round(days * 24))
        log.debug(f"Returning lowest price per day for type id {type_id}")
        return rows

async def pull_fitting_price_data(type_id, pool: asyncpg.Pool, schema: str):
    query = f"""
        SELECT timestamp, type_id, volume_remain, price, is_buy_order
        FROM {schema}.market_orders
        WHERE type_id = $1
          AND is_buy_order = FALSE
        ORDER BY timestamp DESC, price ASC
        LIMIT 1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, type_id)
        return row

async def get_volume(type_id):
    df = pd.read_csv(ITEM_IDS_VOLUME_FILE)
    result = df[df['typeID'] == type_id]['volume']
    return float(result.iloc[0])

async def save_mineral_price(pool: asyncpg.Pool, schema: str, orders, fetched_time):
    reprocess_ids = await load_reprocess_ids()
    log.debug(f"Loaded reprocess_ids as {reprocess_ids}")
    rows_to_insert = [
        (fetched_time, order["type_id"], order["price"])
        for order in orders
        if order["type_id"] in reprocess_ids
    ]
    if not rows_to_insert:
        return
    async with pool.acquire() as conn:
        await conn.executemany(f"""
            INSERT INTO {schema}.mineral_prices (timestamp, type_id, price)
            VALUES ($1, $2, $3)
        """, rows_to_insert)

async def clear_mineral_table(pool: asyncpg.Pool, schema: str):
    async with pool.acquire() as conn:
        await conn.execute(f"DELETE FROM {schema}.mineral_prices")

async def query_recent_price(type_id, pool: asyncpg.Pool, schema: str):
    query = f"""
        SELECT timestamp, type_id, volume_remain, price, is_buy_order
        FROM {schema}.market_orders
        WHERE type_id = $1
        AND is_buy_order = FALSE
        ORDER BY timestamp DESC, price ASC
        LIMIT 1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, type_id)
        return row
