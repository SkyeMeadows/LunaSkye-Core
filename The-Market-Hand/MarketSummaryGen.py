import argparse
import os
import pandas as pd
from datetime import datetime, timedelta, timezone
import re
import json
import sys
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
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logs", "MarketSummaryGeneratorLog.txt"),
    filemode='w',
    level=numeric_log_level,
    format='%(asctime)s [%(levelname)s] %(message)s', # Format's the lines as <time> <[Level]> <Message>
    datefmt='%H:%M:%S' 
)

log = logging.getLogger(__name__)

# Log runtime
current_datetime = datetime.now()
log.info(f"Current datetime is: {current_datetime}")

# === Parse CLI arguments ===
parser = argparse.ArgumentParser(description="Generate market graph for a specific item.")
parser.add_argument("--item_id", type=int, required=True)
parser.add_argument("--timeframe", type=int, default=7, help="Number of days of data to include")
args = parser.parse_args()

item_id = args.item_id
timeframe = args.timeframe

# === Setup Paths ===
data_dir = os.path.join(script_dir, "Data")

BRAVE_HOME_volume_path = os.path.join(data_dir, "BRAVE_HOME_volume_data.csv")
GSF_HOME_volume_path = os.path.join(data_dir, "GSF_HOME_volume_data.csv")

systems_paths = {
    "Jita": "jita_sell_5_avg.csv",
    "UALX-3": "BRAVE_HOME_sell_5_avg.csv",
    "C-J6MT": "GSF_HOME_sell_5_avg.csv"
}

# === Setup proper Time ===
now = pd.Timestamp.utcnow()
start_time = now - pd.Timedelta(days=timeframe)

# === The Loop of Price & Volume ===
summary = {}

for system, filename in systems_paths.items():
    filepath = os.path.join(data_dir, filename)

    try:
        df = pd.read_csv(filepath, parse_dates=["timestamp"])
        print("[PASS]: CSV has been read into dataframe", file=sys.stderr)
    except Exception as e:
        summary[system] = {"error:" f"Failed to load file: {e}"}
        print("[ERROR]:" f"Failed to load file: {e}", file=sys.stderr)
        continue

    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d_%H-%M")
    now = pd.Timestamp.utcnow().tz_localize(None)
    start_time = now - pd.Timedelta(days=timeframe)

    print("[PASS]: Converted Time Str's into datetime", file=sys.stderr)

    df = df[(df["item_id"] == item_id) & (df["timestamp"] >= start_time)]
    df = df.sort_values("timestamp")

    print("[PASS]: Sorted timestamp values", file=sys.stderr)

    if df.empty:
        summary[system] = {"error": "No data available"}
        print(f"[ERROR]: Dataframe Empty!", file=sys.stderr)
        continue

    prices = df["price"].dropna()
    start_price = prices.iloc[0]
    end_price = prices.iloc[-1]
    high_price = prices.max()
    low_price = prices.min()
    absolute_change = end_price - start_price
    percent_change = (absolute_change / start_price) * 100

    summary[system] = {
        "start_price": round(start_price, 2),
        "end_price": round(end_price, 2),
        "highest_price": round(high_price, 2),
        "lowest_price": round(low_price, 2),
        "absolute_change": round(absolute_change, 2),
        "change_percent": round(percent_change, 2)
    }

# === Return the Data ===
print(summary, file=sys.stderr)
print(json.dumps(summary))

# === Completion Debug ===
print(f"Script Run Completed.", file=sys.stderr)
exit(0)