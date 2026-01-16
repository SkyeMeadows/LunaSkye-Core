from modules.utils.paths import MARKET_DB_FILE_GSF, MARKET_DB_FILE_JITA
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
    
    if on_page != 1:
        pages_completed = on_page - 1
    else:
        pages_completed = 0

    ESI_MAX_PAGES = 1 # Initilization placeholder
    ETAG = None
    raw_entries = []
    
    last_fetch_time, nextFetch = await load_cache_time()
    now = int(datetime.now(UTC).timestamp())

    if now < nextFetch:
        sleep_for = (nextFetch - now) + 3
        log.debug(f"Respecting ESI cache: sleeping {sleep_for:.1f}s before fetching page {on_page}")
        await asyncio.sleep(sleep_for)

    while (((OVERRIDE_MAX_ESI_PAGES == 0) or (pages_completed < OVERRIDE_MAX_ESI_PAGES)) and (pages_completed < ESI_MAX_PAGES)):
        
        headers = {
            "Authorization": f'Bearer {token["access_token"]}',
            "Content-Type": "application/json",
            "User-Agent": "LunaSkye Core (admin contact: skyemeadows20@gmail.com)",
            "If-None-Match": ETAG
        }
        url_gsf = f"https://esi.evetech.net/markets/structures/{gsf_structure_id}?page={on_page}"
        url_jita = f"https://esi.evetech.net/latest/markets/10000002/orders/?order_type=all&page={on_page}"
        page_data = []

        if market == "gsf":
            url = url_gsf
        elif market == "jita":
            url = url_jita
        else:
            log.warning(f"Both Markets completed, but scripted is attempting to run again")
            break

        try:
            response = requests.get(url, headers=headers, timeout=10)
            log.debug(f"Response code from page {on_page}: {response.status_code}")

            if response.status_code == 401:
                log.error(f"Recieved 401 response, token is invalid")
                raise ESISessionError(f"ESI Token Invalid, on page {on_page}", errors=on_page)

            allowed_errors_left = int(response.headers.get("X-ESI-Error-Limit-Remain", 0))
            log.debug(f"ESI Allowed Errors Remaining: {allowed_errors_left}")
            error_reset = int(response.headers.get("X-ESI-Error-Limit-Reset", 0))
            log.debug(f"ESI Error Limit Reset in: {error_reset} seconds")

            ESI_MAX_PAGES = int(response.headers.get("X-Pages"))
            log.debug(f"On page {on_page} of {ESI_MAX_PAGES} | {ESI_MAX_PAGES - on_page} pages left")

            expires_header = response.headers.get("expires")
            log.debug(f"expires header: {expires_header}")

            server_time = response.headers.get("Date")
            log.debug(f"Server time header: {server_time}")

            expires_dt = parsedate_to_datetime(response.headers.get("expires", ""))

            last_fetch_time = datetime.now(UTC)
            nextAllowedFetch = expires_dt + timedelta(seconds=3)

            if nextAllowedFetch.tzinfo is None:
                nextAllowedFetch = nextAllowedFetch.replace(tzinfo=UTC)
            nextFetch = nextAllowedFetch.timestamp()

            if response.headers.get("ETag") != ETAG:
                ETAG = response.headers.get("ETag")
                log.debug(f"ETag for page {on_page} set to {ETAG}")
            else:
                log.debug(f"ETag for page {on_page} unchanged.")

            if response.status_code == 200:
                page_data = response.json()
                raw_entries.extend(page_data)

            elif response.status_code == 304:
                log.debug(f"Received 304 for Jita Order on Page {on_page}.")

            else:
                log.error(f"Received unhandled response code {response.status_code} when fetching Jita orders on page {on_page}")
                raise Exception(f"Unhandled response code: {response.status_code}")

        except ESISessionError as e:
            raise


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

        pages_completed += 1
        on_page += 1
    
    if isinstance(raw_entries, bytes):
        raw_entries = json.loads(raw_entries.decode('utf-8'))

    orders = []
    for order in raw_entries:
        if (market == "gsf") or order.get("location_id") == jita_hub_station_id:
            orders.append({
                "type_id": order.get("type_id"),
                "volume_remain": order.get("volume_remain"),
                "price": order.get("price"),
                "is_buy_order": order.get("is_buy_order"),
            })
            
    return orders, last_fetch_time



async def main():
    log.info("Starting market requestor")

    try:
        log.debug(f"Attempting to test ESI Status")
        ESI_online, token = await test_esi_status()
        log.debug(f"ESI Online?: {ESI_online}")
    except Exception as e:
        log.critical(f"Failed to establish ESI session, exception: {e}")

    log.debug(f"Loading ore list")
    ore_list = await load_ore_list()
    log.debug(f"Loaded ore list")

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

    exit(0)
    
asyncio.run(main())