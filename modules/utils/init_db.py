import aiosqlite

async def init_db(DB_PATH):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS market_orders (
                timestamp TEXT NOT NULL,
                type_id INTEGER NOT NULL,
                volume_remain INTEGER NOT NULL,
                price REAL NOT NULL,
                is_buy_order BOOLEAN NOT NULL
            )
        """)
        await db.commit()