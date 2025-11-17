import argparse
import asyncio
import os
from pickle import MARK
import time
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from datetime import datetime, timedelta
from matplotlib.dates import DayLocator, DateFormatter, HourLocator, AutoDateLocator
from matplotlib.ticker import MaxNLocator
import logging
from dotenv import load_dotenv
import aiosqlite
from collections import defaultdict

script_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(script_dir, "Logs"), exist_ok=True)

def get_log_path(logname: str) -> str:
    logs_base_dir = os.path.join(script_dir, "Logs")
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d---%H-%M-%S")
    logs_date_dir = os.path.join(logs_base_dir, today_str)
    os.makedirs(logs_date_dir, exist_ok=True)
    
    logs_filename = f"{logname}---{now_str}.log"
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
    filename=get_log_path("GraphGenerator"),
    filemode='w',
    level=numeric_log_level,
    format='%(asctime)s [%(levelname)s] %(message)s', # Format's the lines as <time> <[Level]> <Message>
    datefmt='%H:%M:%S' 
)

log = logging.getLogger(__name__)

mpl.set_loglevel("warning")

# Showing what logging is enabled
logging.debug("Logging Enabled - This is Not An Issue")
logging.info("Logging Enabled - This is Not An Issue")
logging.warning("Logging Enabled - This is Not An Issue")
logging.error("Logging Enabled - This is Not An Issue")
logging.critical("Logging Enabled - This is Not An Issue")

# Log runtime
current_datetime = datetime.now()
log.info(f"Current datetime is: {current_datetime}")



# === Parse CLI arguments ===
log.debug("Parsing Arguments")
parser = argparse.ArgumentParser(description="Generate market graph for a specific item.")
parser.add_argument("--item_id", type=int, required=True)
parser.add_argument("--days", type=float, default=0, help="Number of days of data to include")
args = parser.parse_args()
log.debug("Arguments Parsed")

# === Setup paths ===
log.debug("Establishing paths to data")

MAIN_DIR = os.path.dirname(script_dir)
DATA_DIR = os.path.join(MAIN_DIR, "Shared-Content")

ID_DICTONARY_PATH = os.path.join(os.path.dirname(script_dir), "Shared-Content", "Item_IDs.csv")

output_folder = os.path.join(script_dir, "Graphs")
os.makedirs(output_folder, exist_ok=True)


# === Load item names ===
log.debug("Loading list of ItemIDs")
item_df = pd.read_csv(ID_DICTONARY_PATH).drop_duplicates(subset="typeID")

# Open DB Connection
db_path = os.path.join(DATA_DIR, "market_historical_data.db")
print(f"DB Path: {db_path}")

async def connect_to_db(item_id: int, days: int = None,  db_path=db_path):
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        query = """
            SELECT timestamp, item_id, system, price
            FROM market_orders
            WHERE item_id = ?
        """
        params = [item_id]

        if days:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            query += " AND timestamp >= ?"
            params.append(cutoff)

        query += " ORDER BY timestamp ASC"

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return rows


async def match_item_name(item_id: int) -> str:
    matched_row = item_df[item_df["typeID"] == item_id]
    if not matched_row.empty:
        print(matched_row)
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {item_id} not found in Item_IDs.csv")


async def make_graph(item_id, days, type_name, db=db_path):
    rows = await connect_to_db(item_id, days, db)

    data_by_system = defaultdict(lambda: {"timestamps": [], "prices": []})

    for row in rows:
        print(f"DEBUG ROW: {row}")
        dt = datetime.fromisoformat(row["timestamp"])
        data_by_system[row["system"]]["timestamps"].append(dt)
        data_by_system[row["system"]]["prices"].append(row["price"])

    plt.figure(figsize=(20,12), dpi=300)
    for system, data in data_by_system.items():
        plt.plot(data["timestamps"], data["prices"], label=system)
    plt.title(f"{type_name} Prices - Last {days} Days")
    plt.xlabel("Timestamp")
    plt.ylabel("Price (ISK)")
    plt.legend()
    plt.tight_layout()
    os.makedirs(os.path.join(script_dir, "Graphs"), exist_ok=True)
    plt.savefig(f"{script_dir}/Graphs/{type_name}_price_graph.png")
    plt.close()


async def main():
    item_id = args.item_id
    days = args.days if args.days > 0 else None
    #db = await connect_to_db(item_id, days)
    type_name = await match_item_name(item_id)

    await make_graph(item_id, days, type_name)


if __name__ == "__main__":
    asyncio.run(main())
