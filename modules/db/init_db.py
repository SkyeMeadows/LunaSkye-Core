import asyncpg

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
