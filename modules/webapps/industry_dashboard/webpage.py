import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from quart import Quart, request, Response, render_template, redirect
from modules.utils.paths import DB_DSN
from modules.utils.logging_setup import get_logger

log = get_logger("IndustryDashboard")

load_dotenv()

testing_mode = os.getenv("TESTING_MODE")

app = Quart(__name__)
db_pool: asyncpg.Pool = None

@app.before_serving
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DB_DSN)

@app.after_serving
async def shutdown():
    await db_pool.close()

@app.route("/", methods=["GET", "POST"])
async def index():
    return await render_template("index.html")

@app.before_request
async def enforce_https():
    if testing_mode:
        return
    if request.scheme != "https":
        url = request.url.replace("http://", "https://", 1)
        return redirect(url, code=301)    

if __name__ == "__main__":
    if testing_mode:
        app.run(debug=True, host="0.0.0.0", port=5003)
    else:
        app.run(debug=True, host="0.0.0.0", port=5003, certfile='server.crt', keyfile='server.key')