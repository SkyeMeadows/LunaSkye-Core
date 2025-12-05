from modules.utils.paths import TOKEN_FILE, RUNTIME_CACHE_PATH
from modules.utils.logging_setup import get_logger
from dotenv import load_dotenv
import json
import time as t
from datetime import datetime, timedelta, UTC, timezone
import aiofiles, aiohttp
import os
from requests_oauthlib import OAuth2Session

log = get_logger("ESI-SessionController")

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

async def load_esi_token(path=TOKEN_FILE):
    with open(path, "r") as file:
        log.debug("Loading ESI Token")
        content = file.read()
        token = json.loads(content)
        return token

async def save_token(new_token):
    async with aiofiles.open(TOKEN_FILE, "w") as f:
        await json.dump(new_token, f) 
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