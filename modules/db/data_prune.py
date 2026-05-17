import asyncpg
import asyncio
from dotenv import load_dotenv
from modules.utils.logging_setup import get_logger
from modules.utils.paths import DB_DSN

log = get_logger("DataPrune")

load_dotenv()

SCHEMAS = ["jita", "gsf", "plex"]

async def prune_old_data(pool: asyncpg.Pool, schema: str):
    command = f"""
        DELETE FROM {schema}.market_orders
        WHERE timestamp < NOW() - INTERVAL '30 days'
        AND EXTRACT(HOUR FROM DATE_TRUNC('hour', timestamp + INTERVAL '30 minutes'))
            NOT IN (0, 4, 8, 12, 16, 20)
    """
    async with pool.acquire() as conn:
        result = await conn.execute(command)
        deleted_count = int(result.split()[-1])
        log.info(f"Pruned {deleted_count} rows from {schema}.market_orders")

async def main():
    pool = await asyncpg.create_pool(DB_DSN)
    for schema in SCHEMAS:
        await prune_old_data(pool, schema)
    await pool.close()

asyncio.run(main())
