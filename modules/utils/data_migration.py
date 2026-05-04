import sqlite3, asyncio, asyncpg
from modules.utils.paths import DB_DSN
from modules.utils.init_db import init_db

MIGRATIONS = [
    #("/home/skye/LunaSkye-Core/data/jita_market_prices.db", "jita"),
    #("/home/skye/LunaSkye-Core/data/gsf_market_prices.db",  "gsf"),
    ("/home/skye/LunaSkye-Core/data/plex_market_prices.db", "plex"),
]

async def migrate(src_path, schema, pool):
    src = sqlite3.connect(src_path)
    rows = src.execute("SELECT timestamp, type_id, volume_remain, price, is_buy_order FROM market_orders").fetchall()
    # SQLite stored timestamps as ISO strings — convert to datetime
    from datetime import datetime, timezone
    converted = [
        (datetime.fromisoformat(r[0]).replace(tzinfo=timezone.utc), r[1], r[2], r[3], bool(r[4]))
        for r in rows
    ]
    async with pool.acquire() as conn:
        await conn.executemany(
            f"INSERT INTO {schema}.market_orders (timestamp, type_id, volume_remain, price, is_buy_order) VALUES ($1,$2,$3,$4,$5)",
            converted
        )
    print(f"{schema}: inserted {len(converted)} rows")
    src.close()

ALL_SCHEMAS = ["jita", "gsf", "plex"]

async def main():
    pool = await asyncpg.create_pool(DB_DSN)

    print("Ensuring schemas and tables exist...")
    for schema in ALL_SCHEMAS:
        await init_db(pool, schema)
        print(f"  {schema}: ready")

    for path, schema in MIGRATIONS:
        await migrate(path, schema, pool)

    await pool.close()

asyncio.run(main())