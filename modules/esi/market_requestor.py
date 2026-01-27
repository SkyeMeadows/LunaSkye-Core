from modules.utils.paths import MARKET_DB_FILE_GSF, MARKET_DB_FILE_JITA, MARKET_DB_FILE_PLEX
from modules.utils.logging_setup import get_logger
from dotenv import load_dotenv
import json
import time as t
from datetime import datetime, timedelta, UTC
from email.utils import parsedate_to_datetime
import os
import requests
import asyncio
from modules.esi.session_control import load_cache_time, load_esi_token
from modules.esi.at_manager import establish_esi_session, test_esi_status
from modules.esi.data_control import save_orders, save_ore_orders, clear_mineral_table, save_mineral_price
from modules.utils.ore_controller import load_ore_list, calculate_ore_value

log = get_logger("MarketRequestor")

load_dotenv()
STATUS_CACHE_DURATION = os.getenv("ESI_STATUS_CACHE_DURATION")
CLIENT_ID = os.getenv("ESI_CLIENT_ID")
CLIENT_SECRET = os.getenv("ESI_CLIENT_SECRET")
TOKEN_URL = os.getenv("ESI_TOKEN_URL")
query_jita_bool = os.getenv("QUERY_JITA_BOOL")
if query_jita_bool == "True":
    query_jita_bool = True
else: 
    query_jita_bool = False
query_gsf_bool = os.getenv("QUERY_GSF_BOOL")
if query_gsf_bool == "True":
    query_gsf_bool = True
else: 
    query_gsf_bool = False
query_plex_bool = os.getenv("QUERY_PLEX_BOOL")
if query_plex_bool == "True":
    query_plex_bool = True
else: 
    query_plex_bool = False
last_esi_status_check_time = 0
cached_status = None
OVERRIDE_MAX_ESI_PAGES = int(os.getenv("OVERRIDE_MAX_ESI_PAGES"))

jita_region_id = 10000002 # The Forge
jita_hub_station_id = 60003760 # Jita 4-4
gsf_structure_id = 1049588174021 # C-J Keepstar

class ESISessionError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors

async def fetch_all_orders(token, market, on_page=1):
    
    # === Checking to see if resuming from other page ===
    if on_page != 1:
        pages_completed = on_page - 1
    else:
        pages_completed = 0

    # === Initilization placeholders ===
    ESI_MAX_PAGES = 1 
    ETAG = None
    raw_entries = []
    
    # === Checking last run time to ensure not over-using ESI resources ===
    last_fetch_time, nextFetch = await load_cache_time()
    now = int(datetime.now(UTC).timestamp())
    if now < nextFetch:
        sleep_for = (nextFetch - now) + 3
        log.debug(f"Respecting ESI cache: sleeping {sleep_for:.1f}s before fetching page {on_page}")
        await asyncio.sleep(sleep_for)

    # === === ===
    # Running main loop to gather ESI data
    # === === ===
    while (((OVERRIDE_MAX_ESI_PAGES == 0) or (pages_completed < OVERRIDE_MAX_ESI_PAGES)) and (pages_completed < ESI_MAX_PAGES)):
        
        # === Establishing ESI Headers to ensure compliance ===
        log.debug("Establishing ESI Headers")
        headers = {
            "Authorization": f'Bearer {token["access_token"]}',
            "Content-Type": "application/json",
            "User-Agent": "LunaSkye Core (admin contact: skyemeadows20@gmail.com)",
            "If-None-Match": ETAG
        }
        url_gsf = f"https://esi.evetech.net/markets/structures/{gsf_structure_id}?page={on_page}"
        url_jita = f"https://esi.evetech.net/latest/markets/10000002/orders/?order_type=all&page={on_page}"
        url_plex = f"https://esi.evetech.net/latest/markets/19000001/orders/?order_type=all&page={on_page}"
        page_data = []

        # === Setting the request URL to match the intended market ===
        log.debug(f"Establishing correct URL for {market}")
        if market == "gsf":
            url = url_gsf
            log.debug("URL set to GSF URL")
        elif market == "jita":
            url = url_jita
            log.debug("URL set to Jita URL")
        elif market == "plex":
            url = url_plex
            log.debug("URL set to PLEX URL")
        else:
            log.warning("All Markets completed, but scripted is attempting to run again")
            break

        # === Attempting to gather ESI Data ===
        try:
            # Makes Request
            response = requests.get(url, headers=headers, timeout=10)
            log.debug(f"Response code from page {on_page}: {response.status_code}")

            # If Token is expire, malformed, or otherwise invalid
            if response.status_code == 401:
                log.error(f"Recieved 401 response, token is invalid")
                raise ESISessionError(f"ESI Token Invalid, on page {on_page}", errors=on_page)

            # Setting error limits
            allowed_errors_left = int(response.headers.get("X-ESI-Error-Limit-Remain", 0))
            log.debug(f"ESI Allowed Errors Remaining: {allowed_errors_left}")
            error_reset = int(response.headers.get("X-ESI-Error-Limit-Reset", 0))
            log.debug(f"ESI Error Limit Reset in: {error_reset} seconds")

            # Finding how many pages are avilable and setting the max page limit to be equal to it.
            ESI_MAX_PAGES = int(response.headers.get("X-Pages"))
            log.debug(f"On page {on_page} of {ESI_MAX_PAGES} | {ESI_MAX_PAGES - on_page} pages left")

            # Getting when the data expires to know when it can be checked next
            expires_header = response.headers.get("expires")
            log.debug(f"expires header: {expires_header}")
            server_time = response.headers.get("Date")
            log.debug(f"Server time header: {server_time}")
            expires_dt = parsedate_to_datetime(response.headers.get("expires", ""))
            last_fetch_time = datetime.now(UTC)
            nextAllowedFetch = expires_dt + timedelta(seconds=3)

            # Only setting next allowed fetch if it is not already set (to avoid overriding the actual earliest time it can be fetched again)
            if nextAllowedFetch.tzinfo is None:
                nextAllowedFetch = nextAllowedFetch.replace(tzinfo=UTC)
            nextFetch = nextAllowedFetch.timestamp()

            # Checkign ETAG to ensure page is not duplicate
            if response.headers.get("ETag") != ETAG:
                ETAG = response.headers.get("ETag")
                log.debug(f"ETag for page {on_page} set to {ETAG}")
            else:
                log.debug(f"ETag for page {on_page} unchanged.")

            # 200 OK
            if response.status_code == 200:
                page_data = response.json()
                raw_entries.extend(page_data)

            # 3XX - Data is elsewhere
            elif response.status_code == 304:
                log.debug(f"Received 304 for Jita Order on Page {on_page}.")

            # ??? - Unhandled Error
            else:
                log.error(f"Received unhandled response code {response.status_code} when fetching Jita orders on page {on_page}")
                raise Exception(f"Unhandled response code: {response.status_code}")

        except ESISessionError as e:
            raise

        # Counting errors to ensure I don't anger the ESI gods
        except Exception as e:
            log.error(f"Error fetching {market} orders on page {on_page}: {e}")
            allowed_errors_left -= 1
            continue
        if allowed_errors_left <= 5:
            log.warning(f"Approaching ESI error limit, pausing for {error_reset} seconds")
            await t.sleep(error_reset + 1)
        if allowed_errors_left <= 0:
            log.critical(f"Exceeded maximum allowed errors when fetching Jita orders")
            break

        # Successfully made it through a page, counting up and will move to next page if next page exists
        pages_completed += 1
        on_page += 1
    # === === ===
    # Main Loop Complete
    # === === ===
    
    # === Returning data in List format ===
    # Transforming data in json
    if isinstance(raw_entries, bytes):
        raw_entries = json.loads(raw_entries.decode('utf-8'))

    # Appending each orders' contents to LIST format
    orders = []
    for order in raw_entries:
        if (market == "gsf") or order.get("location_id") == jita_hub_station_id:
            orders.append({
                "type_id": order.get("type_id"),
                "volume_remain": order.get("volume_remain"),
                "price": order.get("price"),
                "is_buy_order": order.get("is_buy_order"),
            })
    
    # Returning the list of orders & the time at which all data can be fetched again
    return orders, last_fetch_time



async def main():
    log.info("Starting market requestor")

    # Checking ESI Status
    try:
        log.debug(f"Attempting to test ESI Status")
        ESI_online, token = await test_esi_status()
        log.debug(f"ESI Online?: {ESI_online}")
    except Exception as e:
        log.critical(f"Failed to establish ESI session, exception: {e}")

    # Loading TypeID list for all ORE IDs
    log.debug(f"Loading ore list")
    ore_list = await load_ore_list()
    log.debug(f"Loaded ore list")

    log.debug(f"Boolean to for checking Jita is {query_jita_bool}")
    log.debug(f"Boolean to for checking GSF is {query_gsf_bool}")
    log.debug(f"Boolean to for checking PLEX is {query_plex_bool}")

    if query_jita_bool == True:
        log.debug(f"Attemtping to gather Jita data")
        # Attempting to Gather Jita Data
        try:
            jita_orders, last_fetch_time = await fetch_all_orders(token, "jita")
            await save_orders(MARKET_DB_FILE_JITA, jita_orders, last_fetch_time)
            await save_mineral_price(MARKET_DB_FILE_JITA, jita_orders, last_fetch_time)
            for ore_id in ore_list:
                ore_price = await calculate_ore_value(ore_id, MARKET_DB_FILE_JITA)
                await save_ore_orders(MARKET_DB_FILE_JITA, ore_price, last_fetch_time, ore_id)
            await clear_mineral_table(MARKET_DB_FILE_JITA)
            log.info(f"Completed Jita Query")
        except ESISessionError as e:
            log.warning(f"Recieved ESISessionError as {e}")
            if e.errors:
                log.debug(f"Failed on page {e.errors}")
                on_page = e.errors
            log.debug("Attemping to re-establish ESI Session")
            await establish_esi_session()
            token = await load_esi_token()
            log.info(f"Attempting to resume query where left off for jita (page {on_page})")
            await fetch_all_orders(token, "jita", on_page)
    
    if query_gsf_bool == True:
        log.debug(f"Attemtping to gather GSF data")
        # Attempting to Gather GSF Data
        try:
            log.debug(f"Attempting to fetch all orders for GSF with token {token}")
            gsf_orders, last_fetch_time = await fetch_all_orders(token, "gsf")
            await save_orders(MARKET_DB_FILE_GSF, gsf_orders, last_fetch_time)
            await save_mineral_price(MARKET_DB_FILE_GSF, gsf_orders, last_fetch_time)
            for ore_id in ore_list:
                ore_price = await calculate_ore_value(ore_id, MARKET_DB_FILE_GSF)
                await save_ore_orders(MARKET_DB_FILE_GSF, ore_price, last_fetch_time, ore_id)
            await clear_mineral_table(MARKET_DB_FILE_GSF)
            log.info(f"Completed GSF Query")
        except ESISessionError as e:
            log.warning(f"Recieved ESISessionError as {e}")
            if e.errors:
                log.debug(f"Failed on page {e.errors}")
                on_page = e.errors
            log.debug("Attemping to re-establish ESI Session")
            await establish_esi_session()
            token = await load_esi_token()
            log.info(f"Attempting to resume query where left off for GSF (page {on_page})")
            gsf_orders, last_fetch_time = await fetch_all_orders(token, "gsf", on_page)
            await save_orders(MARKET_DB_FILE_GSF, gsf_orders, last_fetch_time)
            await save_mineral_price(MARKET_DB_FILE_GSF, gsf_orders, last_fetch_time)
            for ore_id in ore_list:
                ore_price = await calculate_ore_value(ore_id, MARKET_DB_FILE_GSF)
                await save_ore_orders(MARKET_DB_FILE_GSF, ore_price, last_fetch_time, ore_id)
            await clear_mineral_table(MARKET_DB_FILE_GSF)

    if query_plex_bool == True:
        # Attempting to Gather PLEX Data
        log.debug(f"Attemtping to gather PLEX data")
        try:
            log.debug(f"Attempting to fetch all orders for PLEX with token {token}")
            plex_orders, last_fetch_time = await fetch_all_orders(token, "plex")
            await save_orders(MARKET_DB_FILE_PLEX, plex_orders, last_fetch_time)
            log.info(f"Completed PLEX Query")
        except ESISessionError as e:
            log.warning(f"Recieved ESISessionError as {e}")
            if e.errors:
                log.debug(f"Failed on page {e.errors}")
                on_page = e.errors
            log.debug("Attemping to re-establish ESI Session")
            await establish_esi_session()
            token = await load_esi_token()
            log.info(f"Attempting to resume query where left off for PLEX (page {on_page})")
            plex_orders, last_fetch_time = await fetch_all_orders(token, "plex", on_page)
            await save_orders(MARKET_DB_FILE_PLEX, plex_orders, last_fetch_time)

    exit(0)
    
asyncio.run(main())