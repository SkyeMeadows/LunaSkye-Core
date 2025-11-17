import asyncio
import json
from datetime import datetime
import logging
import subprocess
import discord
import os
from discord import app_commands
from discord.ext import commands
from typing import Literal  # For fixed choices
import pandas as pd
from dotenv import load_dotenv
from collections import defaultdict
import time
import sys

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
    filename=get_log_path("MarketHand"),
    filemode='w',
    level=numeric_log_level,
    format='%(asctime)s [%(levelname)s] %(message)s', # Format's the lines as <time> <[Level]> <Message>
    datefmt='%H:%M:%S' 
)

log = logging.getLogger(__name__)

# Log runtime
current_datetime = datetime.now()
log.info(f"Current datetime is: {current_datetime}")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="!", intents=intents)

### COOLDOWNS
cooldowns = defaultdict(float)
COOLDOWN_SECONDS = 5

log.debug("Discord bot Started")

### PATHS
venv_python = sys.executable
MAIN_DIR = os.path.dirname(script_dir)

token_path = os.path.join(script_dir, "token.json")
item_ids_path = os.path.join(script_dir, "Item_IDs.csv")
graphs_folder = os.path.join(script_dir, "Graphs")
requestor_path = os.path.join(script_dir, "GraphRequestor.py")
requestor_daily_path = os.path.join(script_dir, "GraphRequestorDaily.py")
summary_path = os.path.join(script_dir, "MarketSummaryGen.py")

jita_path = os.path.join(MAIN_DIR, "ESI-Interface", "Data", "jita_sell_5_avg.csv")
BRAVE_HOME_path = os.path.join(MAIN_DIR, "ESI-Interface", "Data", "BRAVE_HOME_sell_5_avg.csv")
GSF_HOME_path = os.path.join(MAIN_DIR, "ESI-Interface", "Data", "GSF_HOME_sell_5_avg.csv")

query_list_path = os.path.join(MAIN_DIR, "Shared-Content", "query_list.json")
item_id_path = os.path.join(MAIN_DIR, "Shared-Content", "Item_IDs.csv")

log.debug("Paths Set")

### Items Available
def load_query_list(path=query_list_path):
    with open(path, "r") as file:
        log.debug("Query List Loading")
        return set (json.load(file))

available_item_ids = load_query_list()

log.debug("Loading Item IDs")
item_df = pd.read_csv(item_id_path).drop_duplicates(subset="typeID")
name_to_id = {
    row["typeName"].lower(): row["typeID"]
    for _, row in item_df.iterrows()
}

available_item_names = []

for itemID in available_item_ids:
    row = item_df[item_df['typeID'] == itemID]

    if not row.empty:
        item_name = row.iloc[0]['typeName']
        available_item_names.append(item_name)

@bot.tree.command(name="shutdown", description="Shuts down the bot (admin only)")
async def shutdown(interaction: discord.Interaction):

    if interaction.guild is None:
        await interaction.response.send_message("This command can't be used in DMs.", ephemeral=True)
        return
    
    if interaction.user.id == 305861137440833536:  # skyecat__
        log.critical("SHUTDOWN COMMAND GIVEN")
        await interaction.response.send_message("Shutting down...", ephemeral=True)
        await bot.change_presence(status=discord.Status.offline)  # Set offline before closing
        await bot.close()
    else:
        await interaction.response.send_message("You do not have permission!", ephemeral=True)

@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()  # Sync slash commands with Discord
        log.info(f"Synced {len(synced)} commands")
    except Exception as e:
        log.error(f"Error syncing commands: {e}")

@bot.tree.command(name="print_item_list", description="See the list of supported items for graphing.")
async def print_item_list(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = time.time()

    if now < cooldowns[user_id]:
        retry_after = cooldowns[user_id] - now
        await interaction.response.send_message(
            f"You're on cooldown! Try again in `{retry_after:.1f}` seconds.",
            ephemeral=True
        )
        return
    else:
        cooldowns[user_id] = now + COOLDOWN_SECONDS
    
    await interaction.response.send_message(available_item_names)

@bot.tree.command(name="query_item_list", description="[CASE SENSITIVE] Look for a specific item in the supported item list")
async def query_item_list(interaction: discord.Interaction, user_item: str):
    user_id = interaction.user.id
    now = time.time()

    if now < cooldowns[user_id]:
        retry_after = cooldowns[user_id] - now
        await interaction.response.send_message(
            f"You're on cooldown! Try again in `{retry_after:.1f}` seconds.",
            ephemeral=True
        )
        return
    else:
        cooldowns[user_id] = now + COOLDOWN_SECONDS

    user_item = user_item.strip()

    if len(user_item) > 50:
        await interaction.response.send_message("Input too long!", ephemeral=True)
        return
    
    if user_item in available_item_names:
        await interaction.response.send_message(f"*{user_item}* **IS** Supported")
        return
    
    df = pd.read_csv("Item_IDs.csv").drop_duplicates(subset="typeID")
    if not (df['typeName'] == user_item).any():
        await interaction.response.send_message(f"*{user_item}* is **INVALID**")
        return
    
    else:
        await interaction.response.send_message(f"*{user_item}* is **NOT** Supported")
        return
    
@bot.tree.command(name="get_item_id")
async def get_item_id(interaction: discord.Interaction, user_item: str):
    user_id = interaction.user.id
    now = time.time()

    if now < cooldowns[user_id]:
        retry_after = cooldowns[user_id] - now
        await interaction.response.send_message(
            f"You're on cooldown! Try again in `{retry_after:.1f}` seconds.",
            ephemeral=True
        )
        return
    else:
        cooldowns[user_id] = now + COOLDOWN_SECONDS
    
    user_item = user_item.strip()

    if len(user_item) > 50:
        await interaction.response.send_message("Input too long!", ephemeral=True)
        return
    
    df = pd.read_csv(item_id_path).drop_duplicates(subset="typeID")
    for itemID in df:
        row = item_df[item_df['typeID'] == itemID]

    match = df[df["typeName"] == user_item]
    if not match.empty:
        itemID = match.iloc[0]["typeID"]
        await interaction.response.send_message(f"The Item ID of **{user_item}** is *{itemID}*")

    
@bot.tree.command(name="get_graph", description="Sends a price graph for the selected item and time range.")
@app_commands.describe(
    item_name="The name of the item you are looking for",
    days_history="How many days of data you want?"
    )
async def get_graph(
    interaction: discord.Interaction,
    item_name: str,
    days_history: float
):
    user_id = interaction.user.id
    now = time.time()

    if now < cooldowns[user_id]:
        retry_after = cooldowns[user_id] - now
        await interaction.response.send_message(
            f"You're on cooldown! Try again in `{retry_after:.1f}` seconds.",
            ephemeral=True
        )
        return
    else:
        cooldowns[user_id] = now + COOLDOWN_SECONDS

    user_input_name = item_name.strip().lower()
    
    if len(user_input_name) > 50:
        await interaction.response.send_message("Input too long!", ephemeral=True)
        return

    await interaction.response.defer()

    async def inner():
        item_key = item_name.strip().lower()
        if item_key not in name_to_id:
            await interaction.followup.send(
                f"Item '{item_name}' not found. Please use the exact in-game name.",
                ephemeral=True
            )
            return

        item_id = name_to_id[item_key]
        safe_item_name = user_input_name.strip().replace(" ", "_").replace("/", "_")

        '''
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d_%H-%M", errors="coerce")
        oldest_date = df["timestamp"].min()
        if pd.isna(oldest_date):
            log.warning("No valid timestamps in the column. Resorting to 0 max_days")
            log.debug(f"Dataframe is: {df}")
            max_days = 0  # or some fallback
        else:
            now = pd.Timestamp.utcnow().tz_localize(None)
            oldest_date = oldest_date.tz_localize(None)
            max_days = (now - oldest_date).days
        
        if days_history > max_days:
            await interaction.followup.send(
                f" Only {max_days} days of data available for **{item_name}**.\n"
                f"Showing what’s available.",
                ephemeral=True
            )
        '''
        #if daily == False:
        command = [
            venv_python,
            requestor_path,
            "--item_id", str(item_id),
            "--days", str(days_history)
        ]
        #log.debug(f"[DEBUG] Running subprocess: {' '.join(command)}")

        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        log.debug(result.stdout)
        log.debug(result.stderr)

        if result.returncode != 0:
            await interaction.followup.send(
                f" Graph could not be generated for **{item_name}**.",
                ephemeral=True
            )
            return
        '''
        if daily == True:
            command = [
                venv_python,
                requestor_daily_path,
                "--item_id", str(item_id),
                "--days", str(days_history),
                "--daily"
            ]
            #log.debug(f"[DEBUG] Running subprocess: {' '.join(command)}")

            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
            log.debug(result.stdout)
            log.debug(result.stderr)

            if result.returncode != 0:
                await interaction.followup.send(
                    f" Graph could not be generated for **{item_name}**.",
                    ephemeral=True
                )
                return
        '''
        days_str = f"{days_history:.1f}"
        filename = f"{safe_item_name}_price_graph.png"
        file_path = os.path.join("Graphs", filename)

        if not os.path.isfile(file_path):
            await interaction.followup.send(
                f" Expected graph file not found: `{filename}`",
                ephemeral=True
            )
            return

        max_days = 0

        await interaction.followup.send(
            content=(
                f"Here's the price graph for **{item_name}** "
                f"(last {days_history} days out of <insert max days> available):"
            ),
            file=discord.File(file_path)
        )

    try:
        await asyncio.wait_for(inner(), timeout=60)
    except asyncio.TimeoutError:
        await interaction.followup.send("Graph generation took too long (60s timeout).", ephemeral=True)

@bot.tree.command(name="item_summary", description="Get historial trends for the specified item")
async def item_summary(
    interaction: discord.Interaction,
    item_name: str,
    timeframe: int,
):
    user_id = interaction.user.id
    now = time.time()

    if now < cooldowns[user_id]:
        retry_after = cooldowns[user_id] - now
        await interaction.response.send_message(
            f"You're on cooldown! Try again in `{retry_after:.1f}` seconds.",
            ephemeral=True
        )
        return
    else:
        cooldowns[user_id] = now + COOLDOWN_SECONDS

    user_input_name = item_name.strip().lower()
    
    if len(user_input_name) > 50:
        await interaction.response.send_message("Input too long!", ephemeral=True)
        return

    await interaction.response.defer()

    async def inner():
        item_key = item_name.strip().lower()
        if item_key not in name_to_id:
            await interaction.followup.send(
                f"Item '{item_name}' not found. Please use the exact in-game name.",
                ephemeral=True
            )
            return
        
        item_id = name_to_id[item_key]

        all_data = []
        for csv_path in [jita_path, BRAVE_HOME_path, GSF_HOME_path]:
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.floor("H").dt.strftime("%Y-%m-%d_%H-%M")
                df = df[df["item_id"] == item_id]
                all_data.append(df)
            
        combined = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
        if combined.empty:
            await interaction.followup.send(f"ISSUE: No data at all for **{item_name}**.", ephemeral=True)
            return
        
        now = pd.Timestamp.utcnow().tz_localize(None)

        df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d_%H-%M", errors="coerce")
        oldest_date = pd.to_datetime(df["timestamp"].min()).tz_localize(None)
        max_days = (now - oldest_date).days

        if timeframe > max_days:
            await interaction.followup.send(
                f" Only {max_days} days of data available for **{item_name}**.\n"
                f"Showing what’s available.",
                ephemeral=True
            )

        command = [
            venv_python,
            str(summary_path),
            "--item_id", str(item_id),
            "--timeframe", str(timeframe),
        ]
        #log.debug(f"[DEBUG] Running subprocess: {' '.join(command)}")

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            summaries = json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            log.error(f"Error: {e.stderr}")
            return    
              
        
        days_returned = min(max_days, timeframe)
        lines = [f"**Market Summary for `{item_name}`** in the last {days_returned} days\n"]

        for system, data in summaries.items():
            if "error" in data:
                lines.append(f"**{system}**: {data['error']}")
                continue

            lines.append(
                f"## System: {system}\n"
                f"Start Price: {data['start_price']:,} ISK\n"
                f"End Price: {data['end_price']:,} ISK\n"
                f"Highest Price: {data['highest_price']:,} ISK\n"
                f"Lowest Price: {data['lowest_price']:,} ISK\n"
                f"Absolute Change in Price: {data['absolute_change']:,} ISK\n"
                f"Percent Change in Price: {data['change_percent']:,}%\n"
            )
        
        message = "\n".join(lines)

        await interaction.followup.send(message)

    try:
        await asyncio.wait_for(inner(), timeout=60)
    except asyncio.TimeoutError:
        await interaction.followup.send("Process took too long (60s timeout).", ephemeral=True)

bot.run(TOKEN)
