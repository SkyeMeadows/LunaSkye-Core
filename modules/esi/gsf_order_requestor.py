from modules.utils.paths import MARKET_DB_FILE_GSF
from modules.utils.logging_setup import get_logger
from dotenv import load_dotenv
import json
import time as t
from datetime import datetime, timedelta, UTC
from email.utils import parsedate_to_datetime
import os
import requests
import asyncio
from modules.esi.session_control import save_cache_time, load_cache_time, load_esi_token, get_authenticated_session
from modules.utils.init_db import init_db
from modules.esi.data_control import save_orders, save_ore_orders
from modules.utils.ore_controller import load_ore_list, calculate_ore_value

log = get_logger("GSFRequestor")

load_dotenv()
STATUS_CACHE_DURATION = os.getenv("ESI_STATUS_CACHE_DURATION")
CLIENT_ID = os.getenv("ESI_CLIENT_ID")
CLIENT_SECRET = os.getenv("ESI_CLIENT_SECRET")
TOKEN_URL = os.getenv("ESI_TOKEN_URL")
last_esi_status_check_time = 0
cached_status = None
OVERRIDE_MAX_ESI_PAGES = 0

gsf_structure_id = 1049588174021 # C-J Keepstar

async def fetch_gsf_orders(token):

    pages_completed = 0
    on_page = 1
    ESI_MAX_PAGES = 1
    ETAG = None
    raw_entries = []

    last_fetch_time, nextFetch = await load_cache_time()
    now = int(datetime.now(UTC).timestamp())

    if now < nextFetch:
        sleep_for = (nextFetch - now) + 3
        log.debug(f"Respecting ESI cache: sleeping {sleep_for:.1f}s before fetching page {on_page}")
        await asyncio.sleep(sleep_for)

    while pages_completed < ESI_MAX_PAGES and (OVERRIDE_MAX_ESI_PAGES == 0 or (pages_completed < OVERRIDE_MAX_ESI_PAGES)):

        headers = {
            "Authorization": f'Bearer {token["access_token"]}',
            "Content-Type": "application/json",
            "User-Agent": "LunaSkye Core (admin contact: skyemeadows20@gmail.com)",
            "If-None-Match": ETAG
        }

        url = f"https://esi.evetech.net/markets/structures/{gsf_structure_id}?page={on_page}"
        page_data = []
 
        try:
            response = requests.get(url, headers=headers, timeout=10)

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
            server_dt  = parsedate_to_datetime(response.headers.get("Date", ""))

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

            if response.status_code == 304:
                log.debug(f"Received 304 for Order on Page {on_page}.")

            elif response.status_code == 401:
                log.error(f"Recieved 401 response, token is invalid")
                log.debug("Atttempting to refresh token")
                try:
                    esi_session = await get_authenticated_session()
                except Exception as e:
                    log.critical(f"Failed to refresh ESI session after 401 response: {e}")
                    raise

            elif response.status_code == 200:
                page_data = response.json()
                raw_entries.extend(page_data)

            else:
                log.error(f"Received unhandled response code {response.status_code} when fetching Jita orders on page {on_page}")
                raise Exception(f"Unhandled response code: {response.status_code}")

        except Exception as e:
            log.error(f"Error fetching Jita orders on page {on_page}: {e}")
            allowed_errors_left -= 1
            continue

        if allowed_errors_left <= 0:
            log.critical(f"Exceeded maximum allowed errors when fetching Jita orders")
            break

        if allowed_errors_left <= 5:
            log.warning(f"Approaching ESI error limit, pausing for {error_reset} seconds")
            await t.sleep(error_reset + 1)

        pages_completed += 1
        on_page += 1

    if isinstance(raw_entries, bytes):
        raw_entries = json.loads(raw_entries.decode('utf-8'))

    ore_list = await load_ore_list()

    raw_entries = [order for order in raw_entries if order["type_id"] in ore_list]

    gsf_orders = []
    for order in raw_entries:        
        
        gsf_orders.append({
            "type_id": order.get("type_id"),
            "volume_remain": order.get("volume_remain"),
            "price": order.get("price"),
            "is_buy_order": order.get("is_buy_order"),
        })

    await save_cache_time(last_fetch_time, nextFetch)

    return gsf_orders, last_fetch_time

async def main():
    log.info("Starting GSF Requestor")

    await init_db(MARKET_DB_FILE_GSF)
    token = await load_esi_token()
    gsf_orders, last_fetch_time = await fetch_gsf_orders(token)
    await save_orders(MARKET_DB_FILE_GSF, gsf_orders, last_fetch_time)

    ore_list = await load_ore_list()

    for ore_id in ore_list:
        ore_price = await calculate_ore_value(ore_id, MARKET_DB_FILE_GSF)
        await save_ore_orders(MARKET_DB_FILE_GSF, ore_price, last_fetch_time, ore_id)

asyncio.run(main())