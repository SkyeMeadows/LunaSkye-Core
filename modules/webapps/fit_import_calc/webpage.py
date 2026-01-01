import pandas as pd
import re
from flask import Flask, render_template, request
from modules.utils.logging_setup import get_logger
from modules.utils.paths import MARKET_DB_FILE_GSF, MARKET_DB_FILE_JITA, ITEM_IDS_FILE
from modules.utils.id_mapping import map_id_to_name, map_name_to_id
from modules.esi.data_control import pull_recent_data

log = get_logger("FittingImportCalc-Web")


log.warning("Using jita data as testing fallback")
DB_PATH = MARKET_DB_FILE_JITA

SECTION_NAMES = ["low", "medium", "high", "rigs", "cargo"]

qty_re = re.compile(r'\s+x(?P<qty>\d+)\s*$')   # matches " ... x42" at end

async def parse_line(line):
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

    item_id = await map_name_to_id(name)

    price_pull = await pull_recent_data(item_id, DB_PATH)
    price = price_pull[0]["price"]
    subtotal = price * qty
    log.debug(f"Got price: {price} for {item_id} ({name}) with a quantity of {qty} and a subtotal of {subtotal}")

    return {"name": name, "qty": qty, "id": item_id, "price": price, "subtotal": subtotal}

async def split_into_blocks(text, ignore_first_line=True):
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

async def parse_input(text, ignore_first_line=True):
    blocks = await split_into_blocks(text, ignore_first_line=ignore_first_line)
   
    item_tracker = {}

    for i, block in enumerate(blocks):
        section = SECTION_NAMES[i] if i < len(SECTION_NAMES) else f"extra_{i - len(SECTION_NAMES) + 1}"
        
        for line in block:
            item = await parse_line(line)
            if item and item["id"] is not None:  
                item_id = item["id"]
                name = item["name"]
                qty = item["qty"]
                price = item["price"]
                subtotal = item["subtotal"]

                if item_id in item_tracker:
                    item_tracker[item_id]["qty"] += qty
                    item_tracker[item_id]["subtotal"] = (item_tracker[item_id]["price"] * item_tracker[item_id]["qty"])
                    if section not in item_tracker[item_id]["sections"]:
                        item_tracker[item_id]["sections"].append(section)
                else:
                    item_tracker[item_id] = {
                        "name": name,
                        "qty": qty,
                        "id": item_id,
                        "price": price,
                        "subtotal": subtotal,
                        "sections": [section]
                    }

    parsed = {}
    for item_data in item_tracker.values():
        primary_section = item_data["sections"][0]
        if primary_section not in parsed:
            parsed[primary_section] = []
        parsed[primary_section].append({
            "name": item_data["name"],
            "qty": item_data["qty"],
            "id": item_data["id"],
            "price": item_data["price"],
            "subtotal": item_data["subtotal"]
        })

    return parsed

app = Flask(__name__)
@app.route("/", methods=["GET","POST"])
async def index():
    result = None
    if request.method == "POST":
        user_input = request.form.get("fitting", "")
        if user_input.strip():
            result = await parse_input(user_input)
    return render_template("index.html", parsed=result)



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)