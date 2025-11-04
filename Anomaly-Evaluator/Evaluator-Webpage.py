import pandas as pd
import os
import logging
import re
from flask import Flask, render_template, request
from dotenv import load_dotenv
import aiosqlite
import asyncio
from datetime import UTC, datetime, timedelta



script_dir = os.path.dirname(os.path.abspath(__file__))

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
    filename=get_log_path("AnomParser"),
    filemode='a',
    level=numeric_log_level,
    format='%(asctime)s [%(levelname)s] %(message)s', # Format's the lines as <time> <[Level]> <Message>
    datefmt='%H:%M:%S' 
)

log = logging.getLogger(__name__)

# Log runtime
current_datetime = datetime.now()
log.info(f"Current datetime is: {current_datetime}")

# === BASICS DONE ===
MAIN_DIR = os.path.dirname(script_dir)
DATA_DIR = os.path.join(MAIN_DIR, "Shared-Content")

log.debug("Loading Static Data")

ID_DICTONARY_PATH = os.path.join(os.path.dirname(script_dir), "Shared-Content", "Item_IDs.csv")

log.debug(f"Loading list of ItemIDs from: {ID_DICTONARY_PATH}")
items_df = pd.read_csv(ID_DICTONARY_PATH).drop_duplicates(subset="typeID")
item_lookup = dict(zip(items_df["typeName"], items_df["typeID"]))


# Open DB Connection
db_path = os.path.join(DATA_DIR, "market_historical_data.db")
log.debug(f"DB Path: {db_path}")

async def connect_to_db(item_ids: list[int],  db_path=db_path):
    log.debug(f"Connecting to DB at path {db_path}")
    log.debug(f"Item ID list: {item_ids}")
    async with aiosqlite.connect(db_path) as db:
        log.debug("Connected to DB")
        db.row_factory = aiosqlite.Row
        BATCH_SIZE = 900
        results = []

        log.debug(f"Querying DB for Item IDs: {item_ids}")
        for i in range(0, len(item_ids), BATCH_SIZE):
            batch = item_ids[i:i+BATCH_SIZE]
            placeholders = ", ".join("?" for _ in batch)

            log.debug(f"Estblishing Query for batch {batch}")

            query = f"""
                SELECT timestamp, item_id, system, price
                FROM market_orders
                WHERE item_id IN ({placeholders})
            """

            log.debug(f"Executing Query: {query} with batch: {batch}")

            async with db.execute(query, batch) as cursor:
                log.debug("Fetching all rows from query")
                rows = await cursor.fetchall()
                log.debug(f"Rows after cursor.fetchall(): {rows}")
                log.debug("Extending results with fetched rows")
                results.extend(rows)

        log.debug(f"Returning all fetched rows - total: {len(results)}")
        if not results:
            log.warning("No results found for the given item IDs.")

        return results

async def match_item_name(item_id: int) -> str:
    matched_row = items_df[items_df["typeID"] == item_id]
    if not matched_row.empty:
        return matched_row.iloc[0]["typeName"]
    else:
        log.error(f"Item ID {item_id} not found in Item_IDs.csv")

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
        # Be sure to send what ores were input so it can be queried from the SQlite DB
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
    log.debug(f"Dataframe being returned: {df}")
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







async def enrich_with_prices(parsed_df: pd.DataFrame, item_lookup: dict) -> pd.DataFrame:
    log.debug("Adding prices column")

    rows = await connect_to_db(list(item_lookup.values()))

    data = [dict(row) for row in rows]

    input_df = pd.DataFrame(data)
    log.debug(f"Input DataFrame shape: {input_df.shape}")
    log.debug(f"Input DataFrame columns: {input_df.columns}")
    log.debug(f"Input DataFrame: {input_df}")
    
    log.debug(f"Parsed DataFrame before manipulation: {parsed_df}")

    # Add price + ISK value
    id_map = {v: k for k, v in item_lookup.items()}
    log.debug(f"Item ID Map: {id_map}")

    input_df["ore"] = input_df["item_id"].map(id_map)

    merged_df = pd.merge(input_df, parsed_df, on="ore", how="left")
    log.debug(f"Merged DataFrame: {merged_df}")

    matches = set(input_df["ore"]) & set(parsed_df["ore"])
    log.debug(f"Number of matching ore names: {len(matches)}")
    log.debug(f"Example matches: {list(matches)[:10]}")

    test_row = merged_df[merged_df["ore"] == "Zeolites"]
    log.debug(f"Test row for 'Zeolites': {test_row}")

    test_row = merged_df[merged_df["ore"] == "Brimful Zeolites"]
    log.debug(f"Test row for 'Brimful Zeolites': {test_row}")

    merged_df["isk_per_m3"] = merged_df["price"] * merged_df["volume"] / merged_df["units"]
    log.debug(f"Merged DataFrame after calculating isk_per_m3: {merged_df}")

    '''
    merged_df["isk_per_m3"] = merged_df.apply(
        lambda row: row["isk_total"] / row["volume"] if row["volume"] else None,
        axis=1
    )
        '''

    log.debug(f"Merged DataFrame after adding isk_per_m3: {merged_df}")

    # Handle TOTAL row separately
    if "TOTAL" in merged_df["ore"].values:
        log.debug("Ignoring Total row")
        totals = merged_df[merged_df["ore"] != "TOTAL"].sum(numeric_only=True)
        merged_df.loc[merged_df["ore"] == "TOTAL", "units"] = totals["units"]
        merged_df.loc[merged_df["ore"] == "TOTAL", "volume"] = totals["volume"]
        merged_df.loc[merged_df["ore"] == "TOTAL", "isk_total"] = totals["isk_total"]
        merged_df.loc[merged_df["ore"] == "TOTAL", "price"] = None
        merged_df.loc[merged_df["ore"] == "TOTAL", "isk_per_m3"] = None

        

    return merged_df



@app.route("/", methods=["GET","POST"])
async def index():
    table_html = ""
    if request.method == "POST":
        user_input = request.form.get("oredata", "")
        if user_input.strip():
            df = parse_input(user_input)
            log.debug(f"Parsed user input into dataframe: {df}")
            sum_df = sum_ore(df)
            log.debug(f"Summed dataframe: {sum_df}")
            sum_df = volume_total(sum_df)
            log.debug(f"Totaled Volume dataframe: {sum_df}")
            sum_df = await enrich_with_prices(sum_df, item_lookup)
            log.debug(f"Enriched dataframe with prices: {sum_df}")
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