import asyncio
import json
import aiosqlite
import pandas as pd
from modules.utils.logging_setup import get_logger
from modules.utils.paths import ORE_LIST, REPROCESS_YIELD
from modules.utils.id_mapping import map_id_to_name, map_name_to_id


log = get_logger("OreController")

async def load_ore_list(path=ORE_LIST):
    with open(path, "r") as file:
        log.debug("Loading Ore ID List")
        content = file.read()
        ore_list = json.loads(content)
        return ore_list
    
async def load_reprocess_yield(path=REPROCESS_YIELD):
    with open(path, "r") as file:
        log.debug("Loading Reprocess Yield")
        content = file.read()
        reprocess_yield = json.loads(content)
        return reprocess_yield
    
async def find_reprocess_yield(item_name):
    reprocess_yield = await load_reprocess_yield()
    log.debug(f"Loaded item name as {item_name}")
    
    refined_products = reprocess_yield.get(item_name, {})
    if not refined_products:
        log.warning("No reprocess data found for %s", item_name)
        return {}
    
    refined_products = {name: amt for name, amt in refined_products.items() if amt > 0}

    return refined_products

async def calculate_ore_value(type_id, fresh_orders):
    ore_price = 0

    log.debug(f"Recieved {type_id} as Ore")
    item_name = await map_id_to_name(type_id)
    log.debug(f"Mapped {type_id} to {item_name}")

    reprocess_yield = await find_reprocess_yield(item_name)
    log.debug(f"Returned reprocess yield for {type_id} ({item_name}) as {reprocess_yield}")
    
    for material, amount in reprocess_yield.items():
        if amount <= 0:
            continue
        material_type_id = await map_name_to_id(material)
        log.debug(f"Got material type id for {material} as {material_type_id}")
        material_price = min(
            (order["price"] for order in fresh_orders if order["type_id"] == material_type_id),
            default=0.0
        )

        log.debug(f"Returned price of {material_type_id} ({material}) as {material_price}")
        
         # TODO: Add an Ice Id list so that ice is handled with a batch count of 1 instead of 100
        ore_price += (material_price  * (amount/100) * 0.9062) # 100 units to reprocess, times refining yield
   
    return ore_price