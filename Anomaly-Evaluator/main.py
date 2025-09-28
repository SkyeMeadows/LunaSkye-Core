import pandas as pd
import os
import logging
import datetime
import re
from flask import Flask, render_template, request
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
    filename=os.path.join(script_dir, "Logs", "AnomParser.txt"),
    filemode='a',
    level=numeric_log_level,
    format='%(asctime)s [%(levelname)s] %(message)s', # Format's the lines as <time> <[Level]> <Message>
    datefmt='%H:%M:%S' 
)

log = logging.getLogger(__name__)

# Log runtime
current_datetime = datetime.time()
log.info(f"Current datetime is: {current_datetime}")

# === BASICS DONE ===
MAIN_DIR = os.path.dirname(script_dir)
jita_price_path = os.path.join(MAIN_DIR, "ESI-Interface", "Data", "jita_sell_5_avg.csv")

app = Flask(__name__)

def parse_input(text):
    log.debug("Parsing Input")
    parsed = []
    for line in text.splitlines():
        log.debug("Stripping all lines of trailing space")
        line = line.strip()
        if not line:
            log.debug("Not a proper line, skipping...")
            continue

        log.debug("Splitting text into columns")
        parts = re.split(r"\t+|\s{2,}", line)

        if len(parts) < 3:
            log.debug(f"Skipping bad line: {line}")
            continue

        if len(parts) > 3:
            log.debug("Trimming Columns")
            parts = parts[:3]

        log.debug("Filling Columns with Data")
        name = parts[0].strip()
        amount_units = int(parts[1].replace(",", ""))
        volume = re.match(r"([\d,]+)", parts[2])
        amount_volume = int(volume.group(1).replace(",", ""))

        log.debug("Appending data to dataframe for return")
        parsed.append({
            "ore": name,
            "units": amount_units,
            "volume": amount_volume
        })
    log.debug("Returning full parsed dataframe")
    return pd.DataFrame(parsed)

def sum_ore(df: pd.DataFrame):
    log.debug("Summing relevant value for table")
    return (
        df.groupby("ore", as_index=False)
          .agg({"units": "sum", "volume": "sum"})
          .sort_values("ore")
    )

def volume_total(df: pd.DataFrame) -> pd.DataFrame:
    log.debug("Totaling relevant values")
    totals = {}
    for col in ["units", "volume", "isk_total"]:
        if col in df.columns:
            totals[col] = df[col].sum()

    # Make a row with TOTAL
    log.debug("Creating TOTAL row")
    total_row = {"ore": "TOTAL"}
    log.debug("Filling TOTAL row with Totals")
    total_row.update(totals)

    # Append as a DataFrame row
    log.debug("Adding TOTAL row as a DataFrame row")
    df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
    log.debug("Returning table dataframe with total row")
    return df

def style_table(df: pd.DataFrame):
    log.debug("Styling Table")
    for col in ["units", "volume", "price", "isk_total"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    styler = (
        df.style
        .hide(axis="index")
          .format({
            "Units": "{:,.0f}",       # whole numbers with commas
            "Volume": "{:,.0f}",      # whole numbers with commas
            "Price/Unit": "{:,.2f}",       # 2 decimals, commas
            "Value": "{:,.0f}",   # whole numbers with commas
            "ISK/m³": "{:,.2f}" # 2 decimal places, commas
        })
        .apply(
            lambda row: [
                "font-weight: bold;" if str(row.get("Ore", "")) == "TOTAL" else ""
                for _ in row
            ],
            axis=1
        )
    )
    return styler.to_html(classes="data", index=False)


log.debug("Loading Static Data")
items_df = pd.read_csv(os.path.join(MAIN_DIR, "ESI-Interface", "Item_IDs.csv"))
item_lookup = dict(zip(items_df["typeName"], items_df["typeID"]))

prices_df = pd.read_csv(jita_price_path, parse_dates=["timestamp"])
prices_df = prices_df.sort_values("timestamp", ascending=False)
latest_prices = prices_df.drop_duplicates(subset=["item_id"], keep="first")
price_lookup = dict(zip(latest_prices["item_id"], latest_prices["price"]))


def enrich_with_prices(df: pd.DataFrame, item_lookup: dict, price_lookup: dict) -> pd.DataFrame:
    log.debug("Adding prices column")
    # Add price + ISK value
    df["price"] = df["ore"].map(item_lookup).map(price_lookup)
    df["isk_total"] = df["units"] * df["price"]

    df["isk_per_m3"] = df.apply(
        lambda row: row["isk_total"] / row["volume"] if row["volume"] else None,
        axis=1
    )

    # Handle TOTAL row separately
    if "TOTAL" in df["ore"].values:
        log.debug("Ignoring Total row")
        totals = df[df["ore"] != "TOTAL"].sum(numeric_only=True)
        df.loc[df["ore"] == "TOTAL", "units"] = totals["units"]
        df.loc[df["ore"] == "TOTAL", "volume"] = totals["volume"]
        df.loc[df["ore"] == "TOTAL", "isk_total"] = totals["isk_total"]
        df.loc[df["ore"] == "TOTAL", "price"] = None
        df.loc[df["ore"] == "TOTAL", "isk_per_m3"] = None

    return df




@app.route("/", methods=["GET","POST"])
def index():
    table_html = ""
    if request.method == "POST":
        user_input = request.form.get("oredata", "")
        if user_input.strip():
            df = parse_input(user_input)
            sum_df = sum_ore(df)
            sum_df = volume_total(sum_df)
            sum_df = enrich_with_prices(sum_df, item_lookup, price_lookup)
            sum_df = sum_df.rename(columns={
                "ore": "Ore",
                "units": "Units",
                "volume": "Volume",
                "price": "Price/Unit",
                "isk_total": "Value",
                "isk_per_m3": "ISK/m³"
            })
            table_html = ("<h2>Summarized Totals</h2>" + style_table(sum_df))
    return render_template("index.html", table_html=table_html)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)