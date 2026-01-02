import re
import json
import asyncio
from quart import Quart, request, Response, render_template, redirect
from modules.utils.logging_setup import get_logger
from modules.utils.paths import MARKET_DB_FILE_GSF, MARKET_DB_FILE_JITA, ITEM_IDS_FILE
from modules.utils.id_mapping import map_id_to_name, map_name_to_id
from modules.esi.data_control import pull_fitting_price_data, get_volume

log = get_logger("FittingImportCalc-Web")

SECTION_NAMES = ["low", "medium", "high", "rigs", "cargo"]

qty_re = re.compile(r'\s+x(?P<qty>\d+)\s*$')   # matches " ... x42" at end

parse_sem = asyncio.Semaphore(2)

async def parse_line(line):
    log.debug(f"Processing line: {line}")
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
    log.debug(f"item_id of item in this line mapped to: {item_id}")

    price_jita = 0
    subtotal_jita = 0
    price_pull_jita = await pull_fitting_price_data(item_id, MARKET_DB_FILE_JITA)
    log.debug(f"Pulled price data for Jita: {price_pull_jita}")
    if price_pull_jita:
        price_jita = price_pull_jita[3]
        subtotal_jita = price_jita * qty

    price_gsf = 0
    subtotal_gsf = 0
    price_pull_gsf = await pull_fitting_price_data(item_id, MARKET_DB_FILE_GSF)
    log.debug(f"Pulled price data for GSF: {price_pull_gsf}")
    if price_pull_gsf:
        price_gsf = price_pull_gsf[3]
        subtotal_gsf = price_gsf * qty
    
    if subtotal_gsf != 0:
        markup = subtotal_gsf - subtotal_jita
        log.debug(f"Calculated GSF markup as {markup}")
    else:
        log.warning(f"Zero-Value for GSF subtotal, markup being set to jita subtotal")
        markup = subtotal_jita
    
    volume_pull = await get_volume(item_id)
    volume = volume_pull * qty
    log.debug(f"Got volume for item {item_id} ({name}) as: {volume}")

    log.debug(f"Got price for JITA: {price_jita} for {item_id} ({name}) with a quantity of {qty} and a subtotal of {subtotal_jita}")
    log.debug(f"Got price for GSF: {price_gsf} for {item_id} ({name}) with a quantity of {qty} and a subtotal of {subtotal_gsf}")

    return {"name": name, "qty": qty, "id": item_id, "price_jita": price_jita, 
            "subtotal_jita": subtotal_jita, "price_gsf": price_gsf, "subtotal_gsf": subtotal_gsf, 
            "markup": markup, "volume": volume}

async def split_into_blocks(text, ignore_first_line=True):
    text = text.strip("\n")
    raw_blocks = re.split(r'\n\s*\n', text)

    blocks = []

    for block in raw_blocks:
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip() != ""]
        if lines:
            blocks.append(lines)

    if ignore_first_line and blocks:
        first_block = blocks[0]
        if len(first_block) == 1:
            blocks = blocks[1:]
        else:
            blocks[0] = first_block[1:]
    return blocks



async def parse_input_stream(text, ignore_first_line=True):
    blocks = await split_into_blocks(text, ignore_first_line=ignore_first_line)

    total_items = sum(len(block) for block in blocks)
    processed = 0

    item_tracker = {}

    for i, block in enumerate(blocks):
        section = SECTION_NAMES[i] if i < len(SECTION_NAMES) else f"extra_{i - len(SECTION_NAMES) + 1}"
        
        for line in block:
            item = await parse_line(line)
            processed += 1
            yield {
                "type": "progress",
                "current": processed,
                "total": total_items,
                "item": line.strip(),
                "section": section
            }
            if item and item["id"] is not None:  
                item_id = item["id"]
                name = item["name"]
                qty = item["qty"]
                price_jita = item["price_jita"]
                subtotal_jita = item["subtotal_jita"]
                price_gsf = item["price_gsf"]
                subtotal_gsf = item["subtotal_gsf"]
                markup = item["markup"]
                volume = item["volume"]

                if item_id in item_tracker:
                    item_tracker[item_id]["qty"] += qty
                    item_tracker[item_id]["subtotal_jita"] = (item_tracker[item_id]["price_jita"] * item_tracker[item_id]["qty"])
                    item_tracker[item_id]["subtotal_gsf"] = (item_tracker[item_id]["price_gsf"] * item_tracker[item_id]["qty"])
                    if section not in item_tracker[item_id]["sections"]:
                        item_tracker[item_id]["sections"].append(section)
                else:
                    item_tracker[item_id] = {
                        "name": name,
                        "qty": qty,
                        "id": item_id,
                        "price_jita": price_jita,
                        "subtotal_jita": subtotal_jita,
                        "price_gsf": price_gsf,
                        "subtotal_gsf": subtotal_gsf,
                        "markup": markup,
                        "volume": volume,
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
            "price_jita": item_data["price_jita"],
            "subtotal_jita": item_data["subtotal_jita"],
            "price_gsf": item_data["price_gsf"],
            "subtotal_gsf": item_data["subtotal_gsf"],
            "markup": item_data["markup"],
            "volume": item_data["volume"]
        })

    yield {
    "type": "done",
    "parsed": parsed
    }

app = Quart(__name__)
@app.route("/", methods=["GET", "POST"])
async def index():
    if request.method == "POST":
        form = await request.form
        user_input = form.get("fitting", "")
        if user_input.strip():
            parsed = {}
            async for event in parse_input_stream(user_input):
                if event["type"] == "done":
                    parsed = event["parsed"]
            return await render_template("index.html", parsed=parsed)
    return await render_template("index.html")

@app.route("/stream", methods=["POST"])
async def stream():
    form = await request.form
    user_input = form.get("fitting", "")

    async def generate():
        try:
            item_count = 0

            async for event in parse_input_stream(user_input):
                item_count += 1

                payload = json.dumps(event, separators=(",",":")) + "\n" 
                yield(payload)
                log.debug(f"Yielding: {event.get("item", "done")}")
                await asyncio.sleep(0.01)
            
            if event["type"] == "done":
                log.info(f"Final parsed: {event['parsed']}")
        
        except Exception as e:
            error_event = {
                "type": "error",
                "message": str(e),
            }
            yield json.dumps(error_event) + "\n"
    
    
    
    return Response(
        generate(),
        mimetype="application/json",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx-safe
        },
    )

'''
@app.before_request
async def enforce_https():
    if request.scheme != "https":
        url = request.url.replace("http://", "https://", 1)
        return redirect(url, code=301)'''

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002, certfile='server.crt', keyfile='server.key')