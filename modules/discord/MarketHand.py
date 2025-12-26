import asyncio
import subprocess
import discord
import os
from discord import Optional, app_commands
from discord.ext import commands
from typing import Literal  # For fixed choices
import pandas as pd
from dotenv import load_dotenv
from collections import defaultdict
import time
import sys
from modules.utils.logging_setup import get_logger
from modules.utils.paths import GRAPHS_TEMP_DIR, ITEM_IDS_FILE, GRAPH_GENERATOR, PROJECT_ROOT


log = get_logger("MarketHandBot")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="!", intents=intents)

### COOLDOWNS
cooldowns = defaultdict(float)
COOLDOWN_SECONDS = 5

log.info("Discord bot Started")

### Items Available

log.debug("Loading Item IDs")
item_df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")
name_to_id = {
    row["typeName"].lower(): row["typeID"]
    for _, row in item_df.iterrows()
}

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
    
    df = pd.read_csv(ITEM_IDS_FILE).drop_duplicates(subset="typeID")
    for itemID in df:
        row = item_df[item_df['typeID'] == itemID]

    match = df[df["typeName"] == user_item]
    if not match.empty:
        itemID = match.iloc[0]["typeID"]
        await interaction.response.send_message(f"The Item ID of **{user_item}** is *{itemID}*")

    
@bot.tree.command(name="get_graph", description="Sends a price graph for the selected item and time range.")
@app_commands.describe(
    item_name="The exact name of the item you are looking for",
    market="Which market do you want to query from?",
    days_history="How far back do you want to look in days? (Supports decimals)"
    )
async def get_graph(
    interaction: discord.Interaction,
    item_name: str,
    market: Literal["Jita", "C-J6MT (GSF)"],
    days_history: Optional[float]
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
        
        command = [
            sys.executable,
            str(GRAPH_GENERATOR),
            "--type_id", str(item_id),
            "--market", str(market)
        ]

        if days_history:
            command.append("--days")
            command.append(str(days_history))

        log.debug(f"Running subprocess: {' '.join(command)}")

        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=30, cwd=str(PROJECT_ROOT))
        log.debug(result.stdout)
        log.error(result.stderr)

        if result.returncode == 0:
            file_path = result.stdout.strip()

        if result.returncode != 0:
            await interaction.followup.send(
                f" Graph could not be generated for **{item_name}**.",
                ephemeral=True
            )
            return


        if not os.path.isfile(file_path):
            await interaction.followup.send(
                f" Expected graph file not found: `{file_path}`",
                ephemeral=True
            )
            return
        
        if not days_history:
            days_history = 1

        await interaction.followup.send(
            content=(
                f"Generated price graph for **{item_name}** over the last {days_history} days:"
            ),
            file=discord.File(file_path)
        )

    try:
        await asyncio.wait_for(inner(), timeout=15)
    except asyncio.TimeoutError:
        await interaction.followup.send("Graph generation took too long (15s timeout).", ephemeral=True)


'''
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
'''


bot.run(TOKEN)
