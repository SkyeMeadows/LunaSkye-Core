import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from modules.utils.paths import LOGS_DIR



# Load environment variables from .env file
load_dotenv()



# Establish log file path
today = datetime.now().strftime("%Y-%m-%d")
LOG_DIR_TODAY = LOGS_DIR / today
LOG_DIR_TODAY.mkdir(parents=True, exist_ok=True)




# Get log level from .env file
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
NUMERIC_LOG_LEVEL = LOG_LEVEL_MAP.get(LOG_LEVEL, logging.DEBUG)



# Main Formatter
FORMATTER = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')



# Logger Factory Function
def get_logger(name: str):
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # already configured

    logger.setLevel(NUMERIC_LOG_LEVEL)

    LOG_DIR_PROGRAM = LOG_DIR_TODAY / name
    LOG_DIR_PROGRAM.mkdir(parents=True, exist_ok=True)

    # App-level log
    app_handler = RotatingFileHandler(
        LOG_DIR_PROGRAM / "app.log",
        maxBytes=5_000_000,
        backupCount=5
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(FORMATTER)

    # Error log
    error_handler = RotatingFileHandler(
        LOG_DIR_PROGRAM / "error.log",
        maxBytes=5_000_000,
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(FORMATTER)

    # Console log
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(FORMATTER)
    console_handler.setLevel(NUMERIC_LOG_LEVEL)

    logger.addHandler(app_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)

    return logger
