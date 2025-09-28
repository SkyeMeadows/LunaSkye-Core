import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from datetime import datetime, timedelta
from matplotlib.dates import DayLocator, DateFormatter, HourLocator, AutoDateLocator
from matplotlib.ticker import MaxNLocator
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
DATA_DIR = os.path.join(MAIN_DIR, script_dir, "Data")

jita_path = os.path.join(DATA_DIR, "jita_sell_5_avg.csv")
BRAVE_HOME_path = os.path.join(DATA_DIR, "BRAVE_HOME_sell_5_avg.csv")
GSF_HOME_path = os.path.join(DATA_DIR, "GSF_HOME_sell_5_avg.csv")

output_folder = os.path.join(script_dir, "Graphs")
os.makedirs(output_folder, exist_ok=True)

log.debug("Data paths established")

# === Load and label data ===
log.debug("reading data from CSV to df")
jita_df = pd.read_csv(jita_path)
BRAVE_HOME_df = pd.read_csv(BRAVE_HOME_path)
GSF_HOME_df = pd.read_csv(GSF_HOME_path)

log.debug("Setting df 'System' to respective systems")
jita_df["system"] = "Jita"
BRAVE_HOME_df["system"] = "BRAVE_HOME"
GSF_HOME_df["system"] = "GSF_HOME"

# === Parse timestamps for all sources (EVE format: "%Y-%m-%d_%H-%M")
log.debug("Converting 'timestamp' into datetime")

jita_df["formatted_time"] = pd.to_datetime(jita_df["timestamp"]).dt.floor("H").dt.strftime("%Y-%m-%d_%H-%M")
BRAVE_HOME_df["formatted_time"] = pd.to_datetime(BRAVE_HOME_df["timestamp"]).dt.floor("H").dt.strftime("%Y-%m-%d_%H-%M")
GSF_HOME_df["formatted_time"] = pd.to_datetime(GSF_HOME_df["timestamp"]).dt.floor("H").dt.strftime("%Y-%m-%d_%H-%M")

log.debug("Dropping NA timestamps")
jita_df = jita_df.dropna(subset=["timestamp"])
BRAVE_HOME_df = BRAVE_HOME_df.dropna(subset=["timestamp"])
GSF_HOME_df = GSF_HOME_df.dropna(subset=["timestamp"])

log.debug("Dropping NA prices")
jita_df = jita_df.dropna(subset=["price"])
BRAVE_HOME_df = BRAVE_HOME_df.dropna(subset=["price"])
GSF_HOME_df = GSF_HOME_df.dropna(subset=["price"])

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

# === Checking & fixing Data Types ===
log.debug("Preparing to make 'price' numeric")
jita_data["price"] = pd.to_numeric(jita_data["price"], errors="coerce")
BRAVE_HOME_data["price"] = pd.to_numeric(BRAVE_HOME_data["price"], errors="coerce")
GSF_HOME_data["price"] = pd.to_numeric(GSF_HOME_data["price"], errors="coerce")

item_id = args.item_id
log.debug(f"Filtering for item id: {item_id}")

log.debug("Preparing to filter out all data != to requested item")
log.debug(f"Data before filtering (Jita): {jita_data}")
log.debug(f"Data before filtering (GSF): {GSF_HOME_data}")
log.debug(f"Data before filtering (BRAVE): {BRAVE_HOME_data}")

jita_data = jita_data[jita_data["item_id"] == item_id]
BRAVE_HOME_data = BRAVE_HOME_data[BRAVE_HOME_data["item_id"] == item_id]
GSF_HOME_data = GSF_HOME_data[GSF_HOME_data["item_id"] == item_id]

log.debug("Filtering complete!")
log.debug(f"Data after filtering (Jita): {jita_data}")
log.debug(f"Data after filtering (GSF): {GSF_HOME_data}")
log.debug(f"Data after filtering (BRAVE): {BRAVE_HOME_data}")

# === Set Cutoff ==
log.debug("Setting the current date and time & cutoffs")
now = datetime.now()
log.debug(f"Established time as: {now}")
cutoff = now - timedelta(days=args.days)
log.debug(f"Established cutoff as: {cutoff}")

cutoff = cutoff.strftime("%Y-%m-%d_%H-%M")
log.debug(f"Established formatted cutoff as: {cutoff}")

# === Filter Based on Cutoff ===
jita_data = jita_data[jita_data["formatted_time"] >= cutoff]
BRAVE_HOME_data = BRAVE_HOME_data[BRAVE_HOME_data["formatted_time"] >= cutoff]
GSF_HOME_data = GSF_HOME_data[GSF_HOME_data["formatted_time"] >= cutoff]

log.debug(f"Data after cutoff (Jita): {jita_data}")
log.debug(f"Data after cutoff (GSF): {GSF_HOME_data}")
log.debug(f"Data after cutoff (BRAVE): {BRAVE_HOME_data}")

# === Plot ===
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
