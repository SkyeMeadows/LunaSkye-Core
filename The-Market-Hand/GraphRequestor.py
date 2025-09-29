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
    filename=os.path.join(script_dir, "Logs", "HourlyGraphGeneratorLog.txt"),
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
DATA_DIR = os.path.join(MAIN_DIR, "ESI-Interface", "Data")

ID_DICTONARY_PATH = os.path.join(os.path.dirname(script_dir), "Shared-Content", "Item_IDs.csv")

output_folder = os.path.join(script_dir, "Graphs")
os.makedirs(output_folder, exist_ok=True)


# === Load item names ===
log.debug("Loading list of ItemIDs")
item_df = pd.read_csv(ID_DICTONARY_PATH).drop_duplicates(subset="typeID")

# Open DB Connection
db_path = os.path.join(DATA_DIR, "market_data.db")
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

    plt.figure(figsize=(16,8), dpi=300)
    for system, data in data_by_system.items():
        plt.plot(data["timestamps"], data["prices"], label=system)
    plt.title(f"{type_name} Prices - Last {days} Days")
    plt.xlabel("Timestamp")
    plt.ylabel("Price (ISK)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"Graphs/{type_name}_price_graph.png")



"""
plt.style.use('dark_background')

for df in [jita_data, BRAVE_HOME_data, GSF_HOME_data]:
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

log.debug(f"Data after timestamp conversion (Jita): {jita_data}")
log.debug(f"Data after timestamp conversion (GSF): {GSF_HOME_data}")
log.debug(f"Data after timestamp conversion (BRAVE): {BRAVE_HOME_data}")

log.debug("Plotting")
fig, ax1 = plt.subplots(figsize=(16, 8), dpi=200)

offset = timedelta(minutes=15)
price_markersize = 1

if not jita_data.empty:
    ax1.plot(
        jita_data["timestamp"],
        jita_data["price"],
        label="Jita",
        marker="o",
        linestyle="-",
        color="white",
        markersize=price_markersize,
        zorder=3
    )

else:
    log.warning(f"Jita Data is EMPTY!")
    ax1.plot([], [], label="Jita", marker="o", linestyle="-", color="white")

if not BRAVE_HOME_data.empty:
    ax1.plot(
        BRAVE_HOME_data["timestamp"], 
        BRAVE_HOME_data["price"], 
        label="BRAVE HOME (UALX)", 
        marker="o", 
        linestyle="--",
        color="blue",
        markersize=price_markersize,
        zorder=3
    )

else:
    log.warning(f"BRAVE_HOME Data is EMPTY!")
    ax1.plot([], [], label="BRAVE_HOME", marker="x", linestyle="--", color="blue")

if not GSF_HOME_data.empty:
    ax1.plot(
        GSF_HOME_data["timestamp"], 
        GSF_HOME_data["price"], 
        label="GSF HOME (C-J)", 
        marker="^", 
        linestyle="-.",
        color="yellow",
        markersize=price_markersize,
        zorder=3
    )
    
else:
    log.warning(f"GSF_HOME Data is EMPTY!")
    ax1.plot([], [], label="GSF_HOME", marker="^", linestyle="-.", color="yellow")


label_range = []
if args.days:
    label_range.append(f"{args.days:.1f}d")
range_str = "_".join(label_range) if label_range else "Full"
filename = f"{safe_name.lower()}_last_{range_str}.png"
filepath = os.path.join(output_folder, filename)

jita_data["timestamp"] = pd.to_datetime(jita_data["timestamp"], errors="coerce")
BRAVE_HOME_data["timestamp"] = pd.to_datetime(BRAVE_HOME_data["timestamp"], errors="coerce")
GSF_HOME_data["timestamp"] = pd.to_datetime(GSF_HOME_data["timestamp"], errors="coerce")

min_time = min(
    jita_data["timestamp"].min(),
    BRAVE_HOME_data["timestamp"].min(),
    GSF_HOME_data["timestamp"].min()
)

max_time = max(
    jita_data["timestamp"].max(),
    BRAVE_HOME_data["timestamp"].max(),
    GSF_HOME_data["timestamp"].max()
)

ax1.set_xlim([min_time, max_time])

plt.title(f"{item_name} - Sell Price Over Last {range_str}", color = 'white')
plt.xlabel("Time", color = 'white')
ax1.set_ylabel("Avg of Lowest 5% Sell Price (ISK)", color="white")
ax1.tick_params(axis="y", labelcolor="white")

TICKS = 18

ax1.xaxis.set_major_locator(MaxNLocator(nbins=TICKS))
ax1.xaxis.set_major_formatter(DateFormatter('%b %d\n%H:%M'))
fig.autofmt_xdate(rotation=45)
plt.xticks(fontsize=10)

ax1.legend(loc="upper right", bbox_to_anchor=(1, 1), frameon=False)

all_prices = pd.concat([
    jita_data["price"],
    BRAVE_HOME_data["price"],
    GSF_HOME_data["price"]
])
# Price axis limits (ax1)
ax1.set_ylim(all_prices.min() * 0.98, all_prices.max() * 1.02)

plt.tight_layout()

plt.savefig(filepath, dpi=300, bbox_inches="tight")
plt.close()

'''
log.debug(f"Jita price range:", jita_data["price"].min(), "-", jita_data["price"].max())
log.debug(f"BRAVE_HOME price range:", BRAVE_HOME_data["price"].min(), "-", BRAVE_HOME_data["price"].max())
log.debug(f"GSF_HOME price range:", GSF_HOME_data["price"].min(), "-", GSF_HOME_data["price"].max())
'''
log.info(f"Graph saved to: {filepath}")
exit(0)
"""


async def main():
    item_id = args.item_id
    days = args.days if args.days > 0 else None
    #db = await connect_to_db(item_id, days)
    type_name = await match_item_name(item_id)

    await make_graph(item_id, days, type_name)


if __name__ == "__main__":
    asyncio.run(main())
