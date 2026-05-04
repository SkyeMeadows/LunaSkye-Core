import sqlite3, asyncio, asyncpg
from datetime import datetime, timezone, timedelta
from modules.utils.paths import DB_DSN
from modules.utils.init_db import init_db

MIGRATIONS = [
    ("/home/skye/LunaSkye-Core/data/jita_market_prices.db", "jita"),
    #("/home/skye/LunaSkye-Core/data/gsf_market_prices.db",  "gsf"),
    #("/home/skye/LunaSkye-Core/data/plex_market_prices.db", "plex"),
]

ALL_SCHEMAS = ["jita", "gsf", "plex"]
SNAPSHOT_HOURS = {0, 4, 8, 12, 16, 20}
BATCH_SIZE = 10_000
VACUUM_EVERY = 5  # vacuum SQLite every 50k rows

def keep_row(ts: datetime) -> bool:
    if ts >= datetime.now(timezone.utc) - timedelta(days=30):
        return True
    rounded_hour = (ts + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
    return rounded_hour.hour in SNAPSHOT_HOURS

async def migrate(src_path, schema, pool):
    src = sqlite3.connect(src_path)
    sqlite_count = src.execute("SELECT COUNT(*) FROM market_orders").fetchone()[0]
    print(f"{schema}: {sqlite_count:,} rows in SQLite, migrating with live deletion...")

    last_rowid = 0
    inserted = 0
    skipped = 0
    batch_num = 0

    async with pool.acquire() as conn:
        while True:
            raw_rows = src.execute(
                "SELECT rowid, timestamp, type_id, volume_remain, price, is_buy_order "
                "FROM market_orders WHERE rowid > ? ORDER BY rowid LIMIT ?",
                (last_rowid, BATCH_SIZE)
            ).fetchall()

            if not raw_rows:
                break

            first_rowid = raw_rows[0][0]
            last_rowid  = raw_rows[-1][0]

            to_insert = []
            for r in raw_rows:
                ts = datetime.fromisoformat(r[1]).replace(tzinfo=timezone.utc)
                if keep_row(ts):
                    to_insert.append((ts, r[2], r[3], r[4], bool(r[5])))
                else:
                    skipped += 1

            if to_insert:
                await conn.executemany(
                    f"INSERT INTO {schema}.market_orders "
                    f"(timestamp, type_id, volume_remain, price, is_buy_order) "
                    f"VALUES ($1,$2,$3,$4,$5)",
                    to_insert
                )
                inserted += len(to_insert)

            src.execute("DELETE FROM market_orders WHERE rowid BETWEEN ? AND ?",
                        (first_rowid, last_rowid))
            src.commit()

            batch_num += 1
            if batch_num % VACUUM_EVERY == 0:
                print(f"\n  {schema}: vacuuming SQLite to reclaim disk space...")
                src.execute("VACUUM")

            print(f"  {schema}: {inserted:,} inserted, {skipped:,} pruned...", end="\r")

        pg_count = await conn.fetchval(f"SELECT COUNT(*) FROM {schema}.market_orders")

    src.close()
    print(f"\n{schema}: done — {inserted:,} inserted, {skipped:,} pruned, "
          f"{pg_count:,} total in PostgreSQL")

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
