import json
import aiofiles
import os
from dotenv import load_dotenv
from requests_oauthlib import OAuth2Session
import asyncio
import sys
from modules.utils.paths import ESI_DIR, TOKEN_FILE
from modules.utils.logging_setup import get_logger
from modules.utils.token_gen import CLIENT_ID, TOKEN_URL

log = get_logger("ATManager")

load_dotenv()
CLIENT_ID = os.getenv("ESI_CLIENT_ID")
CLIENT_SECRET = os.getenv("ESI_CLIENT_SECRET")
TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"

async def read_token():
    try:
        async with aiofiles.open(TOKEN_FILE, 'r') as token_file:
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
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        task = loop.create_task(async_save_token(token))
        task.add_done_callback(lambda t: log.error(f"Save token task crashed: {t.exception()}") if t.exception() else None)
    else:
        loop.run_until_complete(async_save_token(token))


async def async_save_token(new_token):
    log.debug(f"Recieved Token to save as: {new_token}")
    try:
        log.debug("Saving Token")
        log.debug(f"Opening token_path for write: {TOKEN_FILE}")
        log.debug(f"token_path dirname exists: {os.path.isdir(os.path.dirname(TOKEN_FILE))}")
        with open(TOKEN_FILE, 'w') as token_file:
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