import json
import numpy as np
from collections import defaultdict
from modules.utils.logging_setup import get_logger
from modules.utils.paths import ORE_LIST, REPROCESS_YIELD, REPROCESS_IDS, ICE_PRODUCT_LIST
from modules.utils.id_mapping import map_id_to_name, map_name_to_id
from modules.esi.data_control import pull_recent_data


log = get_logger("OreController")

async def load_ore_list(path=ORE_LIST):
    with open(path, "r") as file:
        log.debug("Loading Ore ID List")
        content = file.read()
        ore_list = json.loads(content)
        return ore_list

async def load_ice_product_list(path=ICE_PRODUCT_LIST):
    with open(path, "r") as file:
        log.debug(f"Loading Ice Product IDs")
        content = file.read()
        ice_product_list = json.loads(content)
        return ice_product_list
    
async def load_reprocess_yield(path=REPROCESS_YIELD):
    with open(path, "r") as file:
        log.debug("Loading Reprocess Yield")
        content = file.read()
        reprocess_yield = json.loads(content)
        return reprocess_yield
    
async def load_reprocess_ids(path=REPROCESS_IDS):
    with open(path, "r") as file:
        log.debug("Loading Reprocess Yield")
        content = file.read()
        reprocess_ids = json.loads(content)
        return reprocess_ids
    
async def find_reprocess_yield(item_name):
    reprocess_yield = await load_reprocess_yield()
    log.debug(f"Loaded item name as {item_name}")
    
    refined_products = reprocess_yield.get(item_name, {})
    if not refined_products:
        log.warning("No reprocess data found for %s", item_name)
        return {}
    
    refined_products = {name: amt for name, amt in refined_products.items() if amt > 0}

    return refined_products

async def calculate_ore_value(type_id, market):
    ore_price = 0
    material_price = 0
    ice_list = await load_ice_product_list()
    log.debug(f"Returned ice_list as {ice_list}")

    log.debug(f"Recieved {type_id} as Ore")
    item_name = await map_id_to_name(type_id)
    log.debug(f"Mapped {type_id} to {item_name}")

    reprocess_yield = await find_reprocess_yield(item_name)
    log.debug(f"Returned reprocess yield for {type_id} ({item_name}) as {reprocess_yield}")

    mineral_orders = []
    reprocess_ids = await load_reprocess_ids()
    for type_id in reprocess_ids:
        log.debug(f"Pulling orders for ID {type_id}")
        orders = await pull_recent_data(type_id, market)
        mineral_orders.extend(orders)

    mineral_prices = defaultdict(list)
    for row in mineral_orders:
        mineral_prices[row["type_id"]].append(row["price"])
    
    mineral_price_percentile = {
        type_id: np.percentile(prices, 5) if prices else 0.0
        for type_id, prices in mineral_prices.items()
    }
    
    for material, amount in reprocess_yield.items():
        log.debug(f"Got {material}: {amount} for {reprocess_yield.items()}")
        if amount <= 0:
            continue
        material_type_id = await map_name_to_id(material)
        log.debug(f"Got material type id for {material} as {material_type_id}")

        material_price = mineral_price_percentile.get(material_type_id)
            
        log.debug(f"Returned price of {material_type_id} ({material}) as {material_price}")
        
        log.debug(f"Ore Price before adding {material} is {ore_price}")
        if material_type_id in ice_list:
            log.debug(f"Material ({material}) is an ice product, handling accordingly")
            ore_price += (material_price * amount * 0.9062)
        else:
            ore_price += ((material_price  * (amount/100)) * 0.9062) # 100 units to reprocess, times refining yield
        log.debug(f"Ore Price after adding {material} is {ore_price}")
    
    log.debug(f"Calculated ore price of item {type_id} ({item_name}) to be {ore_price}")
   
    return ore_price