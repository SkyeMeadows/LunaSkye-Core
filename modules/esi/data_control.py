import aiosqlite
from modules.utils.ore_controller import load_ore_list, calculate_ore_value
from modules.utils.logging_setup import get_logger

log = get_logger("DataControl")

async def save_orders(database_path, orders, fetched_time):
    ore_list = await load_ore_list()
    rows_to_insert = []
    for order in orders:
        if order["type_id"] in ore_list:
            log.debug(f"Detected ore, type_id is {order["type_id"]}")
            order["price"] = await calculate_ore_value(order["type_id"], orders)
            log.debug(f"Ore value for {order["type_id"]} as {order["price"]}")

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
