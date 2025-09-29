import json
import aiofiles
import requests
import os
from datetime import datetime, time
import logging
from dotenv import load_dotenv
from requests_oauthlib import OAuth2Session
import asyncio
from requests import ReadTimeout
import sys
import pandas as pd
import aiosqlite


## Setup Logging Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(script_dir, "Logs"), exist_ok=True)

def get_log_path(logname: str) -> str:
    logs_base_dir = os.path.join(script_dir, "Logs")
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d---%H-%M-%S")
    logs_date_dir = os.path.join(logs_base_dir, today_str)
    os.makedirs(logs_date_dir, exist_ok=True)
    
    logs_filename = f"{logname}-{now_str}.log"
    return os.path.join(logs_date_dir, logs_filename)


load_dotenv()
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
numeric_log_level = LOG_LEVEL_MAP.get(LOG_LEVEL, logging.DEBUG)

# Setting up Logging
logging.basicConfig(
    filename=get_log_path("MarketDataCollectionLog"),
    filemode='w',
    level=numeric_log_level,
    format='%(asctime)s [%(levelname)s] %(message)s', # Format's the lines as <time> <[Level]> <Message>
    datefmt='%H:%M:%S' 
)

log = logging.getLogger(__name__)

# Showing what logging is enabled
logging.debug("Logging Enabled - This is Not An Issue")
logging.info("Logging Enabled - This is Not An Issue")
logging.warning("Logging Enabled - This is Not An Issue")
logging.error("Logging Enabled - This is Not An Issue")
logging.critical("Logging Enabled - This is Not An Issue")

# Log runtime
current_datetime = datetime.now()
log.info(f"Current datetime is: {current_datetime}")

# Setting Time
now = datetime.utcnow().time()
target_start_time = time(16, 0, 0)
target_end_time = time(16, 55, 0)
log.debug(f"Established time as: {now}")
today = datetime.today()

# File paths
common_folder = os.path.join(os.path.dirname(script_dir), "Shared-Content")
token_path = os.path.join(script_dir, "token.json")
item_ids_path = os.path.join(common_folder, "Item_IDs.csv")
ore_list_path = os.path.join(common_folder, "ore_list.json")
query_list_path = os.path.join(common_folder, "query_list.json")
reprocessing_yield_path = os.path.join(common_folder, "reprocess_yield.json")
log.debug("Filepaths Loaded")
log.info("Local Data Loaded")

# Loading Sensitive Data
CLIENT_ID = os.getenv("ESI_CLIENT_ID")
log.debug("ESI Client ID Loaded")
CLIENT_SECRET = os.getenv("ESI_CLIENT_SECRET")
log.debug("ESI Client Secret Loaded")
REDIRECT_URI = os.getenv("ESI_REDIRECT_URI")
log.debug("ESI Redirect URI Loaded")

# ESI paths
AUTH_BASE = "https://login.eveonline.com/v2/oauth/authorize"
TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
log.debug("ESI Query Path Bases Loaded")

# Database Paths
DB_PATH = os.path.join(common_folder, "market_data.db")

# TOKEN AUTH FUNCTIONS
async def save_token(new_token):
    async with aiofiles.open(token_path, "w") as f: # Open token file in 'write' (will overwrite previous token)
        content = await f.read()
        await json.dump(content, f) # Write token
    log.debug("Token Saved")

async def get_authenticated_session():
    try:
        async with aiofiles.open(token_path, "r") as f:
            content = await f.read()
            token = json.loads(content) # load token file
            log.debug("Token loaded successfully")
    except Exception as e:
        log.critical(f"Failed to load token: {e}")
        raise
    
    log.debug("Token Reading Complete")

    if "access_token" not in token:
        log.critical("Token file missing 'access_token'!")
        raise ValueError("Token file missing 'access_token'.")

    # (IDK how this works)
    esi = OAuth2Session(
        CLIENT_ID,
        token=token,
        auto_refresh_url=TOKEN_URL,
        auto_refresh_kwargs={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
        },
        token_updater = save_token
    )

    log.debug("OAuth2Session Established")

    try:
        test_resp = esi.get("https://esi.evetech.net/latest/status/", timeout=5) # Ping EVE Server status to verify token works
        if test_resp.status_code != 200: # If code is not 200 OK
            log.critical(f"ESI auth failed with status {test_resp.status_code}: {test_resp.text}")
            log.critical(f"Exiting with error code: 100")
            sys.exit(100) # Code 100 = ESI Status failure
        else:
            log.debug("Test to EVE Status successful")
    except Exception as e:
        log.critical(f"Failed to verify token with ESI: {e}")
        raise

    return esi # return the ESI session defined earlier

# DATA FUNCTIONS
async def process_extract_sellOrders(item_id, location_id, is_structure=False, esi_session=None, system_name="Unknown", ESI_MAX_PAGES=2):
    log.debug(f"esi_session at the start: {esi_session}")
    if esi_session is None:
        log.debug("Required to get new session when extracting sell orders")
        try:
            esi_session = await get_authenticated_session() # Go establish a new session if not already established
            log.info("Authenticated session created successfully.")
        except Exception as e:
            log.critical("Failed to create authenticated session:")
            return {"sell_orders": []}
    else:
        log.debug(f"Session passed in: {esi_session}")

    # Getting token for header
    try:
        async with aiofiles.open(token_path, "r") as f:
            content = await f.read()
            token = json.loads(content) # load token file
            log.debug("Token loaded successfully")
    except Exception as e:
        log.critical(f"Failed to load token: {e}")
        raise

    # Header setup (required for compliance)
    headers = {
        "Authorization": f'Bearer {token["access_token"]}',
        "Content-Type": "application/json",
        "User-Agent": "The Market Hand (admin contact: skyemeadows20+EVE@gmail.com)",
    }

    error_count = 0
    errors_detected = 0
    tries = 0
    page = 1 # Marks how many pages are complete
    ESI_MAX_PAGES_REQUESTED = ESI_MAX_PAGES

    log.info(f"Fetching {item_id} from {'structure' if is_structure else 'region'} {location_id} ({system_name})")
    raw_entries = [] # Cleaning to avoid data contaimination

    if is_structure: # This checks to see if the structure is a player-owned (private) structure
        log.debug("Is Player Structure")
        all_data = [] # Cleaning to avoid data contaimination
        while page <= ESI_MAX_PAGES: # This ensures we don't query more data than we need
            log.debug(f"Querying Player Structure Data: page {page}")
            url = f"https://esi.evetech.net/latest/markets/structures/{location_id}/?type_id={item_id}&page={page}" # Setting URL to fetch Data
            log.info(f"Fetching {system_name} market page {page} for item {item_id}...")
            try:
                response = esi_session.get(url, headers=headers, timeout=10)
                if response.status_code == 401:
                    log.critical("Token is invalid, exiting...")
                    log.critical("Program is exiting with error code 101")
                    sys.exit(101)
                if "X-Pages" in response.headers:
                    ESI_MAX_PAGES = min(int(response.headers["X-Pages"]), ESI_MAX_PAGES_REQUESTED)
                    log.debug(f"Max pages available: {response.headers['X-Pages']}, querying up to page {ESI_MAX_PAGES}")
                if response.status_code != 200:
                    log.warning(f"Page {page} failed: {response.status_code}") # Logs warning for any failed items
                    break
                page_data = response.json() # Saves the response to a variable
                if not page_data:
                    break
                all_data.extend(page_data) # Writes the response (variable) to the data to be filtered
                if len(page_data) < 1000: # If there's fewer than 1000 entries (less than 1 page), end the query early
                    break

                errorsleft = int(response.headers.get("X-ESI-Error-Limit-Remain", 0))
                errorreset = int(response.headers.get("X-ESI-Error-Limit-Reset", 0))

            except ReadTimeout as e:
                log.warning(f"Market API request timed out: {e}")
                error_count += 1
                errors_detected += 1
                continue

            if errorsleft < 3:
                break
            elif errorsleft < 10:
                print(
                    f"WARNING: Errors remaining: {errorsleft}. Error limit reset: {errorreset} seconds."
                )
                log.error(f"Errors remaining: {errorsleft}. Error limit reset: {errorreset}")
            
            if response.status_code != 200:
                errors_detected += 1
                error_count += 1

                error_code = response.status_code
                log.error(f"Error detected: {errors_detected} status code: {error_code}")

                error_details = response.json()
                error = error_details["error"]
                log.error(
                    f"Error fetching data from page {page}. status code: {error_code}, details: {error}"
                )

                if tries < 5:
                    log.error(f"error: {error_count}")
                    tries += 1
                    time.sleep(3)
                    continue
                else:
                    print(f"Reached the 5th try and giving up on page {page} for item {item_id} in private structure in {system_name}.")
                    log.error(f"Reached the 5th try and giving up on page {page} for item {item_id} in private structure in {system_name}.")
                    tries = 0
                    continue
            else:
                tries = 0
            try:
                orders = response.json()
                log.info(f"Fetched {len(orders)} orders from page {page}.")
            except ValueError:
                log.error(f"Error decoding JSON response from page {page}.")
                failed_pages_count += 1
                continue
            page += 1

            if not orders:
                log.error(f"No orders found in page {page}.")
                break

        await asyncio.sleep(1)
            
        raw_entries = [entry for entry in all_data if entry.get("type_id") == item_id] # Saved all the order raw data to a variable for filtering

    else: # If it is a public structure (i.e. Jita)
        url = f"https://esi.evetech.net/latest/markets/10000002/orders/?type_id={item_id}&order_type=all" # Setting URL to fetch Data
        all_data = [] # Clearing to ensure clean data
        while page <= ESI_MAX_PAGES:
            try:
                log.info("Retrieving Jita Data")
                log.debug(f"Querying NPC Structure Data: page {page}")
                response = requests.get(url, headers=headers, timeout=10) # Waits up to 10 seconds for a response
                if response.status_code == 401:
                    log.critical("Token is invalid, exiting...")
                    log.critical("Program is exiting with error code 101")
                    sys.exit(101)
                if "X-Pages" in response.headers:
                    max_pages = int(response.headers["X-Pages"])
                    log.debug(f"Max pages: {max_pages}...")
                if response.status_code == 200:
                    raw_entries = response.json() # Saves order data to a variable to be filtered
                else:
                    log.warning(f"Error {response.status_code} for item {item_id}")
            
                errorsleft = int(response.headers.get("X-ESI-Error-Limit-Remain", 0))
                errorreset = int(response.headers.get("X-ESI-Error-Limit-Reset", 0))

            except ReadTimeout as e:
                log.warning(f"Market API request timed out: {e}")
                error_count += 1
                errors_detected += 1
                continue

            if errorsleft < 3:
                break
            elif errorsleft < 10:
                print(
                    f"WARNING: Errors remaining: {errorsleft}. Error limit reset: {errorreset} seconds."
                )
                log.error(f"Errors remaining: {errorsleft}. Error limit reset: {errorreset}")
            
            if response.status_code != 200:
                errors_detected += 1
                error_count += 1

                error_code = response.status_code
                log.error(f"Error detected: {errors_detected} status code: {error_code}")

                error_details = response.json()
                error = error_details["error"]
                log.error(
                    f"Error fetching data from page {page}. status code: {error_code}, details: {error}"
                )
                print(f"Tries: {tries}")
                if tries < 5:
                    log.error(f"error: {error_count}")
                    tries += 1
                    continue
                else:
                    print(f"Reached the 5th try and giving up on page {page} for item {item_id} in public structure in {system_name}.")
                    log.error(f"Reached the 5th try and giving up on page {page} for item {item_id} in public structure in {system_name}.")
                    page += 1
                    tries = 0
                    continue
            else:
                tries = 0
            try:
                orders = response.json()
                log.info(f"Fetched {len(orders)} orders from page {page}.")
            except ValueError:
                log.error(f"Error decoding JSON response from page {page}.")
                failed_pages_count += 1
                continue
            page += 1

            if not orders:
                log.error(f"No orders found in page {page}.")
                break
        
        await asyncio.sleep(1)

    # Gets only sell orders from the saved data from requests
    sell_orders = [
        {
            "order_id": entry["order_id"],
            "price": entry["price"],
            "volume_remain": entry["volume_remain"],
            "location_id": entry["location_id"],
            "is_buy_order": entry["is_buy_order"],
        }
        for entry in raw_entries if entry.get("is_buy_order") is False # Removes buy orders from the data
    ]

    return {
        "sell_orders": sell_orders, # Returns all order data for sell orders
    }

async def calculate_5_percent_sell(sell_orders):
    if not sell_orders: # If there is no data
        log.error("No Valid Data")
        return None

    prices = sorted([entry["price"] for entry in sell_orders]) # Sort by price

    n = max(1, int(len(prices) * 0.05)) # Filter to only the lowest (first) 5% of prices

    lowest_5_percent = prices[:n] # Applies the above filter

    if not lowest_5_percent:
        log.warning("No valid prices in lowest 5% slice")
        return None

    avg_cheapest_price = sum(lowest_5_percent) / len(lowest_5_percent) # Creates the average pice

    return avg_cheapest_price # Returns average price of the requested item's sell order data

async def get_volume_sold(item, region, esi_session):
    if target_start_time <= now < target_end_time:
        log.debug(f"Is is time to query daily volume data")
    else:
        return None
    
    try:
        async with aiofiles.open(token_path, "r") as f:
            content = await f.read()
            token = json.loads(content) # load token file
            log.debug("Token loaded successfully")
    except Exception as e:
        log.critical(f"Failed to load token: {e}")
        raise
    
    headers = {
        "Authorization": f'Bearer {token["access_token"]}',
        "Content-Type": "application/json",
        "User-Agent": "The Market Hand (admin contact: skyemeadows20+EVE@gmail.com)",
    }

    if esi_session is None:
        log.debug("Required to get new session when extracting sell orders")
        try:
            esi_session = await get_authenticated_session() # Go establish a new session if not already established
            log.info("Authenticated session created successfully.")
        except Exception as e:
            log.critical("Failed to create authenticated session:")
            return {"sell_orders": []}
    else:
        log.debug(f"Session passed in: {esi_session}")

    all_data = []
    url = f"https://esi.evetech.net/latest/markets/{region}/history/?datasource=tranquility&type_id={item}"
    
    try:
        log.debug(f"Requesting: {url}")
        response = esi_session.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            log.warning(f"Fetching Volume data for {region} FAILED: {response.status_code}")
            return None
        log.debug(f"Headers: {response.headers}")
        all_data.extend(response.json())

    except Exception as e:
        log.warning(f"Exception occoured while fetching volume data for {region}: {e}")

    log.debug(f"Length of data: {len(all_data)}")
    log.debug(f"Contents of data: {all_data}")

    if not all_data:
        log.warning(f"No volume data for item {item} in region {region}")
        previous_day_volume = 0
    else:
        previous_day_volume = all_data[-1]["volume"]

    volume_data = {
            "date": datetime.today,
            "item_id": item,
            "region": region,
            "volume_sold": previous_day_volume,
        }

    return volume_data

async def calculate_ore_value(ore_id, reprocess_yield_list, price_data_path):

    log.debug("Reading item id CSV")
    item_id_dict = pd.read_csv(item_ids_path)

    log.debug(f"Locating the name for the ore with the typeID: {ore_id}")
    ore_name = item_id_list.loc[item_id_list["typeID"] == ore_id, "typeName"].values[0]
    log.debug(f"Located ore's name as: {ore_name} for typeID {ore_id}")

    log.debug("Gathering refinement data")
    ore_yield = {name: quantity for name, quantity in reprocess_yield_list[ore_name].items() if quantity != 0}
    log.debug(f"Gathered refinement data for {ore_name} as {ore_yield}")

    log.debug("Reading price data")
    price_data = pd.read_csv(price_data_path, parse_dates=["timestamp"])
    log.debug("Price data read")
    log.debug("Sorting values by timestamp")
    price_data = price_data.sort_values("timestamp", ascending=False)
    log.debug("Price values sorted")

    log.debug(f"Getting specifically the minerals from refinement data for {ore_name}")
    refined_materials = ore_yield.keys()
    log.debug("Gathered mineral names from refinement data")

    log.debug("Merging Price data with refinement data")
    price_data_named = price_data.merge(
        item_id_dict, 
        left_on="item_id",
        right_on="typeID",
        how="left"
    )
    log.debug("Data merged")

    filtered_price_data = price_data_named[price_data_named["typeName"].isin(refined_materials)]

    latest_prices = filtered_price_data.drop_duplicates(subset="typeName", keep="first")

    recent_prices = dict(zip(latest_prices["typeName"], latest_prices["price"]))

    ore_value = {}

    for material, quantity in ore_yield.items():
        price = recent_prices.get(material, 0)
        ore_value[material] = quantity * price

    ore_value = (sum(ore_value.values()) * 0.9063) / 100 # Max refine is 90.63%

    return ore_value


### STATIC DATA
JITA_REGION = 10000002
JITA_STATION = 60003760

BRAVE_HOME_REGION = 10000061
BRAVE_HOME_STRUCTURE = 1046664001931

GSF_HOME_REGION = 10000009
GSF_HOME_STRUCTURE = 1049588174021

item_id_list = pd.read_csv(item_ids_path)

async def load_query_list(path=query_list_path):
    async with aiofiles.open(path, "r") as file:
        content = await file.read()
        return json.loads(content)

async def load_ore_list(path=ore_list_path):
    async with aiofiles.open(path, "r") as file:
        content = await file.read()
        return json.loads(content)
    
async def load_reprocessing_yield(path=reprocessing_yield_path):
    async with aiofiles.open(path, "r") as file:
        content = await file.read()
        return json.loads(content)

### File paths
datapath_jita_sell_5_avg = os.path.join(script_dir, "Data", "jita_sell_5_avg.csv")
log.debug("Jita file paths loaded")

datapath_BRAVE_HOME_sell_5_avg = os.path.join(script_dir, "Data", "BRAVE_HOME_sell_5_avg.csv")
datapath_BRAVE_HOME_region_volume = os.path.join(script_dir, "Data", "BRAVE_HOME_region_volume.csv")
log.debug("BRAVE HOME file paths loaded")

datapath_GSF_HOME_sell_5_avg = os.path.join(script_dir, "Data", "GSF_HOME_sell_5_avg.csv")
datapath_GSF_HOME_region_volume = os.path.join(script_dir, "Data", "GSF_HOME_region_volume.csv")
log.debug("GSF HOME file paths loaded")


CSV_Price_Columns = ["timestamp", "item_id", "system", "price"]
CSV_Volume_Sold_Columns = ["date", "item_id", "region", "volume_sold"]
log.debug("CSV Columns loaded")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS market_orders (
                timestamp TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                system TEXT NOT NULL,
                price REAL NOT NULL
            )
        """)
        await db.commit()

async def process_item_jita(items, ore_list, reprocess_yield_list, esi):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        for item in items:
            try:
                log.debug(f"Processing {item} for Jita")
                
                # Check if Item is an ore, if so, handle differently, if not, continue as normal
                log.debug(f"Checking if item ID {item} is an ore")
                if item in ore_list:
                    log.debug(f"Item {item} is an ore")
                    price_data_path = datapath_jita_sell_5_avg

                    log.debug(f"Calculating ore value for {item}")
                    ore_value = await calculate_ore_value(item, reprocess_yield_list, price_data_path)
                    log.debug(f"Calculated value for ore with ID: {item} is {ore_value}")

                    log.debug("Writing Jita data to SQLite Database")
                    await db.execute("""
                        INSERT INTO market_orders (timestamp, item_id, system, price) 
                        VALUES (?, ?, ?, ?)                
                    """, (current_datetime, item, "Jita", ore_value))
                    await db.commit()

                    log.info(f"Jita Data Recorded for {item}, moving to next item")
                    continue

                log.debug("Extracting Jita Sell Orders")
                jita_sell_orders = await process_extract_sellOrders(item, JITA_STATION, is_structure=False, esi_session=esi, system_name="Jita")
                log.debug("Calculating L5PS Jita Sell Orders")
                jita_sell_orders_5_avg = await calculate_5_percent_sell(jita_sell_orders["sell_orders"])
                log.debug("Jita Data pulled and calculated")

                log.debug("Writing Jita data to SQLite Database")
                await db.execute("""
                    INSERT INTO market_orders (timestamp, item_id, system, price)
                    VALUES(?, ?, ?, ?)
                """, (current_datetime, item, "Jita", jita_sell_orders_5_avg))
                await db.commit()

                log.info(f"Jita Data Recorded for {item}, moving to next item")  

            except Exception as e:  
                log.error(f"Exception caught when processsing Jita Item {item}: {e}")


async def process_item_BRAVE_HOME(items, ore_list, reprocess_yield_list, esi):
    log.debug(f"Got {len(items)} items for BRAVE_HOME Processing: {items}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        for item in items:
            try:
                log.debug(f"Checking if item ID {item} is an ore")
                if item in ore_list:
                    log.debug(f"Item {item} is an ore")
                    price_data_path = datapath_BRAVE_HOME_sell_5_avg

                    log.debug(f"Calculating ore value for {item}")
                    ore_value = await calculate_ore_value(item, reprocess_yield_list, price_data_path)
                    log.debug(f"Calculated value for ore with ID: {item} is {ore_value}")

                    log.debug("Writing BRAVE_HOME data to SQLite Database")
                    await db.execute("""
                        INSERT INTO market_orders (timestamp, item_id, system, price) 
                        VALUES (?, ?, ?, ?)                
                    """, (current_datetime, item, "BRAVE_HOME", ore_value))
                    await db.commit()
                        
                    log.debug("BRAVE_HOME CSV Written")

                    log.info(f"BRAVE_HOME Data Recorded for {item}, moving to next item")
                    continue
                # 2) BRAVE_HOME
                ## PRICE
                log.debug(f"Extracting BRAVE HOME Sell Orders with ESI Session: {esi}")
                BRAVE_HOME_sell_orders = await process_extract_sellOrders(item, BRAVE_HOME_STRUCTURE, is_structure=True, esi_session=esi, system_name="BRAVE_HOME")

                if not BRAVE_HOME_sell_orders["sell_orders"]:
                    log.warning(f"No sell orders for item {item} in BRAVE_HOME - skipping.")
                    continue
                
                log.debug("Calculating L5PS BRAVE HOME Sell Orders")
                BRAVE_HOME_sell_orders_5_avg = await calculate_5_percent_sell(BRAVE_HOME_sell_orders["sell_orders"])    

                log.debug("Writing BRAVE_HOME data to SQLite Database")
                await db.execute("""
                    INSERT INTO market_orders (timestamp, item_id, system, price)
                    VALUES(?, ?, ?, ?)
                """, (current_datetime, item, "BRAVE_HOME", BRAVE_HOME_sell_orders_5_avg))
                await db.commit()

                log.info(f"BRAVE HOME Data Recorded for {item}, moving to next item")

            except Exception as e:
                log.warning(f"Failed to process price for item {item} in BRAVE_HOME: {e}")
            
            ## VOLUME 
            """
            if target_start_time <= now < target_end_time:
                log.debug(f"Is is time to query daily volume data")
            else:
                log.debug("Not time to query volume data")
                continue
            
            BRAVE_HOME_volume_sold = await get_volume_sold(item, BRAVE_HOME_REGION, esi)

            volume_sold = BRAVE_HOME_volume_sold["volume_sold"]

            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=CSV_Volume_Sold_Columns)
            if file_is_empty:
                writer.writeheader() # writes from fieldnames above ["date", "item_id", "region", "volume_sold"]
            if BRAVE_HOME_volume_sold is None:
                log.debug("Received No Value, Skipping")
                continue
            writer.writerow({
                "date": today,
                "item_id": item,
                "region": "Tenerefis",
                "volume_sold": volume_sold
            })

            async with aiofiles.open(datapath_BRAVE_HOME_region_volume, mode='a', newline='', encoding='utf-8') as data:
                await data.write(output.getvalue())
                """


async def process_item_GSF_HOME(items, ore_list, reprocess_yield_list, esi):
    log.debug(f"Got {len(items)} items for GSF_HOME Processing: {items}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        for item in items:
            try:
                log.debug(f"Checking if item ID {item} is an ore")
                if item in ore_list:
                    log.debug(f"Item {item} is an ore")
                    price_data_path = datapath_GSF_HOME_sell_5_avg

                    log.debug(f"Calculating ore value for {item}")
                    ore_value = await calculate_ore_value(item, reprocess_yield_list, price_data_path)
                    log.debug(f"Calculated value for ore with ID: {item} is {ore_value}")

                    log.debug("Writing GSF_HOME data to SQLite Database")
                    await db.execute("""
                        INSERT INTO market_orders (timestamp, item_id, system, price)
                        VALUES(?, ?, ?, ?)
                    """, (current_datetime, item, "GSF_HOME", GSF_HOME_sell_orders_5_avg))
                    await db.commit()

                    log.info(f"Jita Data Recorded for {item}, moving to next item")
                    continue

                # 3) GSF_HOME
                ## PRICE
                log.debug(f"Extracting GSF HOME Sell Orders with ESI Session: {esi}")
                GSF_HOME_sell_orders = await process_extract_sellOrders(item, GSF_HOME_STRUCTURE, is_structure=True, esi_session=esi, system_name="GSF_HOME")
                
                if not GSF_HOME_sell_orders["sell_orders"]:
                    log.warning(f"No sell orders for item {item} in GSF_HOME - skipping.")
                    continue
                
                log.debug("Calculating L5PS GSF HOME Sell Orders")
                GSF_HOME_sell_orders_5_avg = await calculate_5_percent_sell(GSF_HOME_sell_orders["sell_orders"])

                log.debug("Writing GSF_HOME data to SQLite Database")
                await db.execute("""
                    INSERT INTO market_orders (timestamp, item_id, system, price)
                    VALUES(?, ?, ?, ?)
                """, (current_datetime, item, "GSF_HOME", GSF_HOME_sell_orders_5_avg))
                await db.commit()
                
                log.info(f"GSF HOME Data Recorded for {item}, moving to next item")
            
            except Exception as e:
                log.warning(f"Failed to process price for item {item} in GSF_HOME: {e}")
            
            ## VOLUME   
            """ 
            if target_start_time <= now < target_end_time:
                log.debug(f"Is is time to query daily volume data")
            else:
                log.debug("Not time to query volume data")
                continue

            GSF_HOME_volume_sold = await get_volume_sold(item, GSF_HOME_REGION, esi)

            volume_sold = GSF_HOME_volume_sold["volume_sold"]

            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=CSV_Volume_Sold_Columns)
            if file_is_empty:
                writer.writeheader() # writes from fieldnames above ["date", "item_id", "region", "volume_sold"]
            if GSF_HOME_volume_sold is None:
                log.debug("Received No Value, Skipping")
                continue
            writer.writerow({
                "date": today,
                "item_id": item,
                "region": "Insmother",
                "volume_sold": volume_sold
            })

            async with aiofiles.open(datapath_GSF_HOME_region_volume, mode='a', newline='', encoding='utf-8') as data:
                await data.write(output.getvalue())
            """
                

async def main():
    log.info("Starting Data Processing")
    query_list = await load_query_list()
    ore_list = await load_ore_list()
    reprocess_yield_list = await load_reprocessing_yield()
    esi = await get_authenticated_session()
    await init_db()
    await asyncio.gather(
        process_item_jita(query_list, ore_list, reprocess_yield_list, esi),
        process_item_BRAVE_HOME(query_list, ore_list, reprocess_yield_list, esi),
        process_item_GSF_HOME(query_list, ore_list, reprocess_yield_list, esi)
    )
    log.info("Data Processing Complete!")

asyncio.run(main())