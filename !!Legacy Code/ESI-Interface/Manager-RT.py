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
    
    logs_filename = f"{logname}---{now_str}.txt"
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
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logs", "RefreshTokenManagerLog.txt"),
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
CLIENT_SECRET = os.getenv("ESI_LIENT_SECRET")
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