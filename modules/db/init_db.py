import asyncio
import sys
import asyncpg
from modules.utils.paths import DB_DSN

async def init_db(pool: asyncpg.Pool, schema: str):
    async with pool.acquire() as conn:
        await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.market_orders (
                timestamp     TIMESTAMPTZ      NOT NULL,
                type_id       INTEGER          NOT NULL,
                volume_remain INTEGER          NOT NULL,
                price         DOUBLE PRECISION NOT NULL,
                is_buy_order  BOOLEAN          NOT NULL
            )
        """)

        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.mineral_prices (
                timestamp TIMESTAMPTZ      NOT NULL,
                type_id   INTEGER          NOT NULL,
                price     DOUBLE PRECISION NOT NULL
            )
        """)

        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{schema}_market_orders
            ON {schema}.market_orders (type_id, timestamp DESC, price ASC)
        """)

async def main():
    schema = sys.argv[1] if len(sys.argv) > 1 else "jita"
    pool = await asyncpg.create_pool(DB_DSN)
    await init_db(pool, schema)
    await pool.close()
    print(f"Initialized schema: {schema}")

if __name__ == "__main__":
    asyncio.run(main())