from modules.utils.logging_setup import get_logger
from modules.utils.ore_controller import calculate_ore_value, load_ore_list
from modules.esi.data_control import save_ore_orders
from modules.utils.init_db import init_db
from modules.utils.paths import MARKET_DB_FILE_GSF, MARKET_DB_FILE_JITA
import asyncio
import aiosqlite
from datetime import datetime, UTC

log = get_logger("Test-Caller")

async def pull_data(type_id):

    async with aiosqlite.connect(MARKET_DB_FILE_GSF) as db:
        db.row_factory = aiosqlite.Row

        query = """
            SELECT timestamp, type_id, price, is_buy_order
            FROM market_orders
            WHERE type_id = ?
            AND is_buy_order = FALSE
            ORDER BY timestamp ASC
        """
    
        params = [type_id]

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return rows
    


async def main():
    log.info("Starting Test Requestor")

    await init_db(MARKET_DB_FILE_GSF)
    await init_db(MARKET_DB_FILE_JITA)

    ore_list = await load_ore_list()

    last_fetch_time = datetime.now(UTC)

    #for ore_id in ore_list:
        #ore_price = await calculate_ore_value(ore_id, MARKET_DB_FILE_GSF)
        #await save_ore_orders(MARKET_DB_FILE_GSF, ore_price, last_fetch_time, ore_id)
    

asyncio.run(main())