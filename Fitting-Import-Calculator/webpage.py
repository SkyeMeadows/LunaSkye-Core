import pandas as pd
import os
import logging
import datetime
import re
from flask import Flask, render_template, request
from dotenv import load_dotenv
from pprint import pprint

script_dir = os.path.dirname(os.path.abspath(__file__))

def get_log_path(logname: str) -> str:
    logs_base_dir = os.path.join(script_dir, "Logs")
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d---%H-%M-%S")
    logs_date_dir = os.path.join(logs_base_dir, today_str)
    os.makedirs(logs_date_dir, exist_ok=True)
    
    logs_filename = f"{logname}-{now_str}.txt"
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
    filename=os.path.join(script_dir, "Logs", "Fitting-Parser.txt"),
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
common_folder = os.path.join(MAIN_DIR, "Shared-Content")
DB_PATH = os.path.join(common_folder, "fitting_data.db")






SECTION_NAMES = ["low", "medium", "high", "rigs", "cargo"]
ITEM_ID_CSV = pd.read_csv(os.path.join(common_folder, "Item_IDs.csv"))
ITEM_IDS = dict(zip(ITEM_ID_CSV["typeName"], ITEM_ID_CSV["typeID"]))

qty_re = re.compile(r'\s+x(?P<qty>\d+)\s*$')   # matches " ... x42" at end

def parse_line(line):
    """Return (name, qty) from a single line. qty defaults to 1."""
    line = line.strip()
    if not line:
        return None
    m = qty_re.search(line)
    if m:
        qty = int(m.group("qty"))
        name = qty_re.sub("", line).strip()
    else:
        qty = 1
        name = line

    item_id = ITEM_IDS.get(name, None)  # look up by exact match

    return {"name": name, "qty": qty, "id": item_id}

def split_into_blocks(text, ignore_first_line=True):
    """
    Split input into blocks separated by one or more blank lines.
    If ignore_first_line is True drop the very first non-empty line (title).
    Returns list of blocks (each block is list of lines).
    """
    # Normalize newlines
    text = text.strip("\n")
    # Split by one-or-more blank lines (keep internal whitespace lines removed)
    raw_blocks = re.split(r'\n\s*\n', text)
    # Trim lines inside blocks and drop empty blocks
    blocks = []
    for block in raw_blocks:
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip() != ""]
        if lines:
            blocks.append(lines)
    if ignore_first_line and blocks:
        # remove first line only (title line), but blocks[0] may contain multiple lines
        # If title is the first line alone, it will become an empty block -> drop it.
        first_block = blocks[0]
        if len(first_block) == 1:
            blocks = blocks[1:]
        else:
            # title and more lines in the first block: drop the first line only
            blocks[0] = first_block[1:]
    return blocks

def parse_input(text, ignore_first_line=True):
    """
    Returns dict with keys for each section present (low, medium, high, rigs, cargo).
    """
    blocks = split_into_blocks(text, ignore_first_line=ignore_first_line)
    parsed = {}
    # assign known section names by order; if there are more blocks than SECTION_NAMES,
    # remaining ones go into "extra_1", "extra_2", ...
    for i, block in enumerate(blocks):
        if i < len(SECTION_NAMES):
            section = SECTION_NAMES[i]
        else:
            section = f"extra_{i - len(SECTION_NAMES) + 1}"
        parsed[section] = []
        for line in block:
            item = parse_line(line)
            if item:
                parsed[section].append(item)
    return parsed

app = Flask(__name__)
@app.route("/", methods=["GET","POST"])
def index():
    parsed = None
    if request.method == "POST":
        user_input = request.form.get("fitting", "")
        if user_input.strip():
            parsed = parse_input(user_input)
    return render_template("index.html", parsed=parsed)



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)