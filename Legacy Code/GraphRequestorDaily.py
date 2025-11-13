import argparse
from logging import log
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from datetime import datetime, timedelta, timezone
from matplotlib.dates import DayLocator, DateFormatter, HourLocator
import logging
from dotenv import load_dotenv

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
    filename=os.path.join(script_dir, "Logs", "DailyGraphGeneratorLog.txt"),
    filemode='w',
    level=numeric_log_level,
    format='%(asctime)s [%(levelname)s] %(message)s', # Format's the lines as <time> <[Level]> <Message>
    datefmt='%H:%M:%S' 
)

mpl.set_loglevel("warning")

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

# === Parse CLI arguments ===
log.debug("Parsing Arguments")
parser = argparse.ArgumentParser(description="Generate market graph for a specific item.")
parser.add_argument("--item_id", type=int, required=True)
parser.add_argument("--days", type=float, default=0, help="Number of days of data to include")
parser.add_argument('--daily', action='store_true')
args = parser.parse_args()
log.debug("Arguments Parsed")

# === Setup paths ===
log.debug("Establish paths to data")

MAIN_DIR = os.path.dirname(script_dir)
DATA_DIR = os.path.join(MAIN_DIR, "ESI-Interface", "Data")

jita_path = os.path.join(DATA_DIR, "jita_sell_5_avg.csv")
BRAVE_HOME_path = os.path.join(DATA_DIR, "BRAVE_HOME_sell_5_avg.csv")
GSF_HOME_path = os.path.join(DATA_DIR, "GSF_HOME_sell_5_avg.csv")

BRAVE_HOME_volume_path = os.path.join(DATA_DIR, "BRAVE_HOME_region_volume.csv")
GSF_HOME_volume_path = os.path.join(DATA_DIR, "GSF_HOME_region_volume.csv")

output_folder = os.path.join(script_dir, "Graphs")
os.makedirs(output_folder, exist_ok=True)

log.debug("Data paths established")

# === Load and label data ===
log.debug("reading data from CSV to df")
jita_df = pd.read_csv(jita_path)
BRAVE_HOME_df = pd.read_csv(BRAVE_HOME_path)
GSF_HOME_df = pd.read_csv(GSF_HOME_path)

log.debug(f"Jita Data after reading CSV: {jita_df}")

log.debug("Setting df 'System' to respective systems")
jita_df["system"] = "Jita"
BRAVE_HOME_df["system"] = "BRAVE_HOME"
GSF_HOME_df["system"] = "GSF_HOME"

log.debug(f"Jita Data after setting system to Jita: {jita_df}")

BRAVE_HOME_volume_df = pd.read_csv(BRAVE_HOME_volume_path)
GSF_HOME_volume_df = pd.read_csv(GSF_HOME_volume_path)

# === Parse timestamps for all sources (EVE format: "%Y-%m-%d_%H-%M")

log.debug("Converting 'timestamp' into datetime")
jita_df["timestamp"] = pd.to_datetime(jita_df["timestamp"], errors="coerce")
BRAVE_HOME_df["timestamp"] = pd.to_datetime(BRAVE_HOME_df["timestamp"], errors="coerce")
GSF_HOME_df["timestamp"] = pd.to_datetime(GSF_HOME_df["timestamp"], errors="coerce")

log.debug(f"Jita Data after setting timestamp to timestamp format: {jita_df}")
log.debug(f"NA Value count in Jita data: {jita_df["timestamp"].isna().sum()}")

log.debug("Dropping NA timestamps")
jita_df = jita_df.dropna(subset=["timestamp"])
BRAVE_HOME_df = BRAVE_HOME_df.dropna(subset=["timestamp"])
GSF_HOME_df = GSF_HOME_df.dropna(subset=["timestamp"])

log.debug(f"Jita Data after dropping NA timestamps: {jita_df}")

BRAVE_HOME_volume_df["date"] = pd.to_datetime(BRAVE_HOME_volume_df["date"]).dt.date
GSF_HOME_volume_df["date"] = pd.to_datetime(GSF_HOME_volume_df["date"]).dt.date


# === Load item names ===
log.debug("Loading list of ItemIDs")
item_df = pd.read_csv(os.path.join(script_dir, "Item_IDs.csv")).drop_duplicates(subset="typeID")
id_to_name = dict(zip(item_df["typeID"], item_df["typeName"]))
item_name = id_to_name.get(args.item_id, f"Item {args.item_id}")
safe_name = item_name.replace(" ", "_").replace("/", "_")

# === Split by system ===
log.debug("sorting df's by timestamp")
jita_data = jita_df.sort_values("timestamp")
BRAVE_HOME_data = BRAVE_HOME_df.sort_values("timestamp")
GSF_HOME_data = GSF_HOME_df.sort_values("timestamp")

log.debug(f"Jita Data after sorting by timestamp: {jita_data}")

BRAVE_HOME_volume_data = BRAVE_HOME_volume_df.sort_values("date")
GSF_HOME_volume_data = GSF_HOME_volume_df.sort_values("date")

# === Checking & fixing Data Types ===
log.debug("Making 'price' numeric")
jita_data["price"] = pd.to_numeric(jita_data["price"], errors="coerce")
BRAVE_HOME_data["price"] = pd.to_numeric(BRAVE_HOME_data["price"], errors="coerce")
GSF_HOME_data["price"] = pd.to_numeric(GSF_HOME_data["price"], errors="coerce")

log.debug(f"Jita Data after setting price to numeric: {jita_data}")

item_id = args.item_id

log.debug("filtering out all data != to requested item")
jita_data = jita_data[jita_data["item_id"] == item_id]
BRAVE_HOME_data = BRAVE_HOME_data[BRAVE_HOME_data["item_id"] == item_id]
GSF_HOME_data = GSF_HOME_data[GSF_HOME_data["item_id"] == item_id]

BRAVE_HOME_volume_data = BRAVE_HOME_volume_data[BRAVE_HOME_volume_data["item_id"] == item_id]
GSF_HOME_volume_data = GSF_HOME_volume_data[GSF_HOME_volume_data["item_id"] == item_id]

# === Set Cutoff ==
log.debug("Setting the current date and time & cutoffs")
now = datetime.now()
cutoff = now - timedelta(days=args.days)
date_cutoff = datetime.today().date() - timedelta(days=args.days)

# === Filter Based on Cutoff ===
jita_data = jita_data[jita_data["timestamp"] >= cutoff]
BRAVE_HOME_data = BRAVE_HOME_data[BRAVE_HOME_data["timestamp"] >= cutoff]
GSF_HOME_data = GSF_HOME_data[GSF_HOME_data["timestamp"] >= cutoff]

BRAVE_HOME_volume_data = BRAVE_HOME_volume_data[BRAVE_HOME_volume_data["date"] >= date_cutoff]
GSF_HOME_volume_data = GSF_HOME_volume_data[GSF_HOME_volume_data["date"] >= date_cutoff]

# === Plot ===
log.debug("Plotting")

plt.style.use('dark_background')

fig, ax1 = plt.subplots(figsize=(16, 8))
price_markersize = 3

bar_width = 0.1
offset = timedelta(hours=1.25)
bar_alpha = 0.5
ax2 = ax1.twinx()

BRAVE_base_dates = pd.to_datetime(BRAVE_HOME_volume_data["date"]).dt.floor("D")
GSF_base_dates = pd.to_datetime(GSF_HOME_volume_data["date"]).dt.floor("D")

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
    print("[DEBUG] Jita Data is EMPTY!")
    ax1.plot([], [], label="Jita", marker="o", linestyle="-", color="white")

print("[DEBUG] BRAVE_HOME raw data shape:", BRAVE_HOME_data.shape)
print("[DEBUG] BRAVE_HOME raw data head\n", BRAVE_HOME_data.head())

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
    ax2.bar(
        BRAVE_base_dates - offset,
        BRAVE_HOME_volume_data["volume_sold"],
        label="BRAVE HOME (UALX)",
        width=bar_width,
        alpha=bar_alpha,
        color="blue",
        zorder=1
    )

else:
    print("[DEBUG] BRAVE_HOME Data is EMPTY!")
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
    ax2.bar(
        GSF_base_dates + offset,
        GSF_HOME_volume_data["volume_sold"],
        label="GSF HOME (C-J)",
        width=bar_width,
        alpha=bar_alpha,
        color="yellow",
        zorder=1
    )
    
else:
    print("[DEBUG] GSF_HOME Data is EMPTY!")
    ax1.plot([], [], label="GSF_HOME", marker="^", linestyle="-.", color="yellow")


label_range = []
if args.days:
    label_range.append(f"{args.days:.1f}d")
range_str = "_".join(label_range) if label_range else "Full"
filename = f"{safe_name.lower()}_last_{range_str}.png"
filepath = os.path.join(output_folder, filename)

min_time = min(jita_data["timestamp"].min(), BRAVE_HOME_data["timestamp"].min(), GSF_HOME_data["timestamp"].min())
max_time = max(jita_data["timestamp"].max(), BRAVE_HOME_data["timestamp"].max(), GSF_HOME_data["timestamp"].max())
time_span = max_time - min_time

if time_span < timedelta(hours=6):
    locator = HourLocator(interval=1)  # Hourly ticks
    formatter = DateFormatter('%H:%M')
elif time_span < timedelta(days=3):
    locator = HourLocator(interval=3)  # Every 3 hours
    formatter = DateFormatter('%b %d\n%H:%M')
elif time_span < timedelta(days=10):
    locator = DayLocator(interval=1)
    formatter = DateFormatter('%b %d')
else:
    locator = DayLocator(interval=2)
    formatter = DateFormatter('%b %d')

plt.title(f"{item_name} - Sell Price Over Last {range_str}", color = 'white')
plt.xlabel("Time", color = 'white')
ax1.set_ylabel("Avg of Lowest 5% Sell Price (ISK)", color = 'white')
ax1.tick_params(axis="y", labelcolor="white")

ax1.xaxis.set_major_locator(locator)
ax1.xaxis.set_major_formatter(formatter)
plt.xticks(rotation=45)

ax2.set_ylabel("Volume Sold in Region")
ax2.tick_params(axis='y')

ax1.legend(loc="upper right", bbox_to_anchor=(1, 1))

all_prices = pd.concat([
    jita_data["price"],
    BRAVE_HOME_data["price"],
    GSF_HOME_data["price"]
])
# Price axis limits (ax1)
ax1.set_ylim(all_prices.min() * 0.98, all_prices.max() * 1.02)

plt.tight_layout()


plt.savefig(filepath)
plt.close()

print("Jita price range:", jita_data["price"].min(), "-", jita_data["price"].max())
print("BRAVE_HOME price range:", BRAVE_HOME_data["price"].min(), "-", BRAVE_HOME_data["price"].max())
print("GSF_HOME price range:", GSF_HOME_data["price"].min(), "-", GSF_HOME_data["price"].max())

print(f"Graph saved to: {filepath}")
exit(0)
