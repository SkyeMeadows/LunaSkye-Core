import aiosqlite

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