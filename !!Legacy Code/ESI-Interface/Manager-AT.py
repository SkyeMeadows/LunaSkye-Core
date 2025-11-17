import json
import aiofiles
from io import StringIO
import requests
import os
from datetime import datetime, timedelta, time
import logging
import csv
from dotenv import load_dotenv
from requests_oauthlib import OAuth2Session
import asyncio
from requests import ReadTimeout
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))

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
    filename=get_log_path("AccessTokenManager"),
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

# Allowing non-HTTPS traffic (should not be used in end production)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

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

SCOPES = [
    "esi-markets.structure_markets.v1",
    "esi-universe.read_structures.v1"
]
log.debug("ESI Scopes Loaded")

# File paths
token_path = os.path.join(script_dir, "token.json")
item_ids_path = os.path.join(script_dir, "Item_IDs.csv")
log.debug("Filepaths Loaded")
log.info("Local Data Loaded")


async def read_token():
    try:
        async with aiofiles.open(token_path, 'r') as token_file:
            content = await token_file.read() # Read file into a string
            token = json.loads(content) # Turn above string into a python data structure
            log.debug("Token Loaded")
    except FileNotFoundError:
        log.critical("Token file does not exist!")
        raise
    except Exception as e:
        log.critical(f"Unhandled error occoured when trying to read the token file: {e}")
        raise

    return token
    

def save_token(token):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If no current loop (e.g. in a new thread)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # Inside an existing async loop — schedule as a background task
        task = loop.create_task(async_save_token(token))
        task.add_done_callback(lambda t: log.error(f"Save token task crashed: {t.exception()}") if t.exception() else None)
    else:
        # No running loop — run the async function now and block until done
        loop.run_until_complete(async_save_token(token))


async def async_save_token(new_token):
    log.debug(f"Recieved Token to save as: {new_token}")
    try:
        log.debug("Saving Token")
        log.debug(f"Opening token_path for write: {token_path}")
        log.debug(f"token_path dirname exists: {os.path.isdir(os.path.dirname(token_path))}")
        with open(token_path, 'w') as token_file:
            json.dump(new_token, token_file, indent=2)
        log.debug("Token Saved")
    except FileNotFoundError:
        log.critical("Token file does not exist!")
        log.warning("Failed to save token")
        raise
    except Exception as e:
        log.error(e)
        raise


async def establish_esi_session():

    try:
        log.debug("Reading token file")
        token = await read_token()
    except FileNotFoundError:
        log.critical("ESI Token file could not be found when establishing ESI Session")
        raise
    except Exception as e:
        log.critical(f"Unhandled error occoured when attempting to read token file when establishing ESI Session: {e}")
        raise

    log.debug("Attempting to establish OAauth2Session")

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

    log.debug("ESI Session Established")

    return esi, token


async def test_esi_status():

    log.debug("Calling ESI Establishment")

    esi, token = await establish_esi_session()

    log.debug("ESI Established")

    status_check_attempts = 0
    ESI_online = False
    while status_check_attempts < 5:
        try:
            status_check_attempts +=1
            test_response = esi.get("https://esi.evetech.net/latest/status/", timeout=10)
            log.debug(f"ESI Status check returned: {test_response}")
            if test_response.status_code == 200:
                log.info("ESI Status: ONLINE")
                ESI_online = True
                break
            else:
                log.warning("ESI Status: OFFLINE")
                await asyncio.sleep(15)
        except Exception as e:
            log.critical(f"Something went wrong trying to verify ESI Status: {e}")
            raise
    
    log.debug(f"Sending ESI Online Status as: {ESI_online}")
    log.debug(f"Sending token as: {token}")
    
    return ESI_online, token


async def main():
    ESI_online, token = await test_esi_status()

    log.debug(f"Recived ESI Online Status as: {ESI_online}")
    log.debug(f"Recived Token as: {token}")
    try:
        if ESI_online == False:
            log.critical("Waited 1+ minute(s) for ESI status, ESI offline, exiting...")
            sys.exit(100)
    except Exception as e:
        print(e)




    
asyncio.run(main())