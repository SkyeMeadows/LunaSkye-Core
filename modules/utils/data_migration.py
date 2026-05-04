import sqlite3, asyncio, asyncpg
from datetime import datetime, timezone, timedelta
from modules.utils.paths import DB_DSN
from modules.utils.init_db import init_db

MIGRATIONS = [
    #("/home/skye/LunaSkye-Core/data/jita_market_prices.db", "jita"),
    ("/home/skye/LunaSkye-Core/data/gsf_market_prices.db",  "gsf"),
    #("/home/skye/LunaSkye-Core/data/plex_market_prices.db", "plex"),
]

ALL_SCHEMAS = ["jita", "gsf", "plex"]
SNAPSHOT_HOURS = {0, 4, 8, 12, 16, 20}
BATCH_SIZE = 10_000

def keep_row(ts: datetime) -> bool:
    if ts >= datetime.now(timezone.utc) - timedelta(days=30):
        return True
    # Round to nearest hour and check if it's a snapshot hour
    rounded_hour = (ts + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
    return rounded_hour.hour in SNAPSHOT_HOURS

async def migrate(src_path, schema, pool):
    src = sqlite3.connect(src_path)
    sqlite_count = src.execute("SELECT COUNT(*) FROM market_orders").fetchone()[0]
    print(f"{schema}: {sqlite_count:,} total rows in SQLite, filtering and inserting...")

    cursor = src.execute(
        "SELECT timestamp, type_id, volume_remain, price, is_buy_order FROM market_orders"
    )

    batch = []
    inserted = 0
    skipped = 0

    async with pool.acquire() as conn:
        while True:
            raw_rows = cursor.fetchmany(BATCH_SIZE)
            if not raw_rows:
                break

            for r in raw_rows:
                ts = datetime.fromisoformat(r[0]).replace(tzinfo=timezone.utc)
                if keep_row(ts):
                    batch.append((ts, r[1], r[2], r[3], bool(r[4])))
                else:
                    skipped += 1

            if batch:
                await conn.executemany(
                    f"INSERT INTO {schema}.market_orders "
                    f"(timestamp, type_id, volume_remain, price, is_buy_order) "
                    f"VALUES ($1,$2,$3,$4,$5)",
                    batch
                )
                inserted += len(batch)
                batch = []
                print(f"  {schema}: {inserted:,} inserted, {skipped:,} skipped...", end="\r")

        pg_count = await conn.fetchval(f"SELECT COUNT(*) FROM {schema}.market_orders")

    src.close()
    print(f"{schema}: done — {inserted:,} inserted, {skipped:,} pruned, {pg_count:,} total in PostgreSQL")

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
