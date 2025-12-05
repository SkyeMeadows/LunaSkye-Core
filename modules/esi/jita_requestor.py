from modules.utils.paths import TOKEN_FILE, ITEM_IDS_FILE, ID_QUERY_LIST, MARKET_DB_FILE_JITA, RUNTIME_CACHE_PATH, MARKET_DB_FILE_JITA, MARKET_DB_FILE_GSF
from modules.utils.logging_setup import get_logger
from dotenv import load_dotenv
import json
import time as t
from datetime import datetime, timedelta, UTC
import aiofiles, aiohttp
import os
from requests_oauthlib import OAuth2Session
import requests
import asyncio
import aiosqlite
from modules.esi.session_control import save_cache_time, load_cache_time, load_query_list, load_esi_token, save_token, get_esi_status, get_authenticated_session

log = get_logger("JitaRequestor")

load_dotenv()
STATUS_CACHE_DURATION = os.getenv("ESI_STATUS_CACHE_DURATION")
CLIENT_ID = os.getenv("ESI_CLIENT_ID")
CLIENT_SECRET = os.getenv("ESI_CLIENT_SECRET")
TOKEN_URL = os.getenv("ESI_TOKEN_URL")
last_esi_status_check_time = 0
cached_status = None
OVERRIDE_MAX_ESI_PAGES = 0

async def save_cache_time(last_fetch_time, nextFetch, path=RUNTIME_CACHE_PATH):
    state = {
        "last_fetch_time": last_fetch_time.isoformat(),
        "nextFetch": nextFetch.total_seconds()
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(state))
    log.debug("Saved cache state")

async def load_cache_time(path=RUNTIME_CACHE_PATH):
    if not path.exists():
        return datetime(1970, 1, 1, tzinfo=UTC), timedelta(seconds=0)

    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            data = json.loads(await f.read())

        last_dt = datetime.fromisoformat(data["last_fetch_time"])
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=UTC)

        return last_dt, timedelta(seconds=float(data["nextFetch"]))
    except:
        return datetime(1970, 1, 1, tzinfo=UTC), timedelta(seconds=0)
        

async def load_query_list(path=ID_QUERY_LIST):
    with open(path, "r") as file:
        log.debug("Loading Item ID Query list")
        return set (json.load(file))

async def load_esi_token(path=TOKEN_FILE):
    with open(path, "r") as file:
        log.debug("Loading ESI Token")
        content = file.read()
        token = json.loads(content)
        return token

async def save_token(new_token):
    async with aiofiles.open(TOKEN_FILE, "w") as f:
        content = await f.read()
        await json.dump(content, f) 
    log.debug("Token Saved")

async def get_esi_status():
    global last_esi_status_check_time, cached_status

    if (t.time() - last_esi_status_check_time) < float(STATUS_CACHE_DURATION) and cached_status is not None:
        log.debug("Using Cached ESI Status")
        return cached_status

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://esi.evetech.net/latest/status/", timeout=5) as response:
                cached_status = await response.json()
                last_esi_status_check_time = t.time()
                return cached_status
        except Exception as e:
            log.error(f"Error fetching ESI status: {e}")
            log.info(f"Due to error, returning cached status if available")
            return cached_status

async def get_authenticated_session():
    try:
        token = await load_esi_token()
        log.debug("Token Loaded for Authenticated Session")
    except FileNotFoundError as e:
        log.critical(f"Token file does not exist! full exception: {e}")
        raise
    except Exception as e:
        log.error(f"Unhandled error occoured when trying to read the token file: {e}")
        raise

    log.debug("Token reading complete")

    if "access_token" not in token:
        log.critical("Token file is missing access_token field!")
        raise KeyError("Token file is missing access_token field!")

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
        test_response = await get_esi_status()
        log.debug(f"ESI Status check returned: {test_response}")
    except Exception as e:
        log.critical(f"Unhandled error when attempting to check ESI status: {e}")
        raise

    return esi


async def fetch_jita_orders(esi_session=None):
    jita_region_id = 10000002 # The Forge
    if esi_session is None:
        try:
            esi_session = await get_authenticated_session()
        except FileNotFoundError as e:
            log.critical(f"Jita fetch failed due to missing token file! full exception: {e}")
            raise
        except Exception as e:
            log.critical(f"Unhandled error when attempting to establish ESI session for Jita order fetching: {e}")
            raise
    else:
        log.debug(f"ESI Session provided already for Jita order fetching")

    try:
        token = await load_esi_token()
        log.debug("Token Loaded for Authenticated Session")
    except FileNotFoundError as e:
        log.critical(f"Token file does not exist! full exception: {e}")
        raise
    except Exception as e:
        log.error(f"Unhandled error occoured when trying to read the token file: {e}")
        raise

    pages_completed = 0
    on_page = 1
    ESI_MAX_PAGES = 1
    ETAG = None
    time_format = "%a, %d %b %Y %H:%M:%S GMT"
    raw_entries = []
    
    last_fetch_time, nextFetch = await load_cache_time()
    age = datetime.now(UTC) - last_fetch_time

    if age < nextFetch:
        sleep_for = (nextFetch - age).total_seconds() + 3
        log.debug(f"Respecting ESI cache: sleeping {sleep_for:.1f}s before fetching page {on_page}")
        await asyncio.sleep(sleep_for)

    while pages_completed < ESI_MAX_PAGES and (OVERRIDE_MAX_ESI_PAGES == 0 or (pages_completed < OVERRIDE_MAX_ESI_PAGES)):

        headers = {
            "Authorization": f'Bearer {token["access_token"]}',
            "Content-Type": "application/json",
            "User-Agent": "LunaSkye Core (admin contact: skyemeadows20@gmail.com)",
            "If-None-Match": ETAG
        }
        url = f"https://esi.evetech.net/latest/markets/10000002/orders/?order_type=all&page={on_page}"
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

            last_fetch_time = datetime.now(UTC)
            nextFetch = datetime.strptime(expires_header, time_format) - datetime.strptime(server_time, time_format) + timedelta(seconds=3)

            if response.headers.get("ETag") != ETAG:
                ETAG = response.headers.get("ETag")
                log.debug(f"ETag for page {on_page} set to {ETAG}")
            else:
                log.debug(f"ETag for page {on_page} unchanged.")

            if response.status_code == 304:
                log.debug(f"Received 304 for Jita Order on Page {on_page}.")

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

    jita_orders = []
    for order in raw_entries:
        if order.get("location_id") == 60003760:
            jita_orders.append({
                "type_id": order.get("type_id"),
                "volume_remain": order.get("volume_remain"),
                "price": order.get("price"),
                "is_buy_order": order.get("is_buy_order"),
            })


    await save_cache_time(last_fetch_time, nextFetch)

    return jita_orders, last_fetch_time

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

async def main():
    log.info("Starting Jita Requestor Test")
    query_list = await load_query_list()
    #ore_list = 
    #reprocess_yield_list = await load_reprocessing_yield()

    await init_db(MARKET_DB_FILE_JITA)

    esi_session = await get_authenticated_session()
    jita_orders, last_fetch_time = await fetch_jita_orders(esi_session=esi_session)
    await save_orders(MARKET_DB_FILE_JITA, jita_orders, last_fetch_time)

asyncio.run(main())