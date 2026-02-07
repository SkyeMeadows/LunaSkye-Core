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
from datetime import datetime, UTC
import time
import sys
from modules.utils.logging_setup import get_logger
from modules.utils.paths import ITEM_IDS_FILE, GRAPH_GENERATOR, PROJECT_ROOT, MARKET_SUMMARY_GENERATOR, PRICE_CHECKER
from modules.market.graph_generator import match_item_name, generate_graph, generate_combined_graph
from modules.market.market_summary_generator import create_summary


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
    market: Literal["Jita", "C-J6MT (GSF)", "PLEX"],
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
        
        type_name = await match_item_name(item_id)
        filepath, display_days, resolved_type_name = await generate_graph(item_id, days_history, market.lower(), type_name)

        if filepath is None:
            await interaction.followup.send(
                f"No data available for **{resolved_type_name}** in the past {days_history} days in {market}.",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            content=(
                f"Generated price graph for **{resolved_type_name}** over the last {display_days} days in {market}:"
            ),
            file=discord.File(filepath)
        )

        if not os.path.isfile(filepath):
            await interaction.followup.send(
                f" Expected graph file not found: `{filepath}`",
                ephemeral=True
            )
            return

    try:
        await asyncio.wait_for(inner(), timeout=30)
    except asyncio.TimeoutError:
        await interaction.followup.send("Graph generation took too long (30s timeout).", ephemeral=True)



@bot.tree.command(name="item_summary", description="Get historial trends for the specified item")
async def item_summary(
    interaction: discord.Interaction,
    item_name: str,
    market: Literal["Jita", "C-J6MT (GSF)", "PLEX"],
    days_history: int
):
    log.debug(f"Command item_summary called with arguments: {item_name}, {market}, {days_history}")
    user_id = interaction.user.id
    now = time.time()
    log.debug(f"Logged time as {now}")

    if now < cooldowns[user_id]:
        log.debug(f"Sending cooldown message to user {interaction.user.display_name}")
        retry_after = cooldowns[user_id] - now
        await interaction.response.send_message(
            f"You're on cooldown! Try again in `{retry_after:.1f}` seconds.",
            ephemeral=True
        )
        log.debug("Cooldown message sent")
        return
    else:
        cooldowns[user_id] = now + COOLDOWN_SECONDS
        log.debug(f"Set user {interaction.user.display_name} cooldown to {now + COOLDOWN_SECONDS} seconds")

    await interaction.response.defer()

    async def inner():
        log.debug(f"Item name recived as {item_name}")
        item_key = item_name.strip().lower()
        log.debug(f"Translated into item key of: {item_key}")
        if item_key not in name_to_id:
            log.debug(f"Item key not found in item_id list")
            await interaction.followup.send(
                f"Item '{item_name}' not found. Please use the exact in-game name.",
                ephemeral=True
            )
            return
        
        item_id = name_to_id[item_key]
        log.debug(f"Set item_id to {item_id}")

        summary_text, display_days, type_name = await create_summary(item_id, days_history, market, item_name)
        
        await interaction.followup.send(
            content=(
                summary_text
            ),
        )

    try:
        await asyncio.wait_for(inner(), timeout=30)
    except asyncio.TimeoutError:
        await interaction.followup.send("Process took too long (30s timeout).", ephemeral=True)


@bot.tree.command(name="check_price", description="Gets the current sell price of an item.")
async def check_price(
    interaction: discord.Interaction,
    item_name: str,
    market: Literal["Jita", "C-J6MT (GSF)", "PLEX"]
):
    log.debug(f"check_price called with arguments {item_name}, {market}")
    user_id = interaction.user.id
    now = time.time()
    log.debug(f"Logged time as {now}")

    if now < cooldowns[user_id]:
        log.debug(f"Sending cooldown message to user {interaction.user.display_name}")
        retry_after = cooldowns[user_id] - now
        await interaction.response.send_message(
            f"You're on cooldown! Try again in `{retry_after:.1f}` seconds.",
            ephemeral=True
        )
        log.debug("Cooldown message sent")
        return
    else:
        cooldowns[user_id] = now + COOLDOWN_SECONDS
        log.debug(f"Set user {interaction.user.display_name} cooldown to {now + COOLDOWN_SECONDS} seconds")

    await interaction.response.defer()

    async def inner():
        log.debug(f"Item Name recieved as {item_name}")
        item_key = item_name.strip().lower()
        log.debug(f"Translated into item key of: {item_key}")
        if item_key not in name_to_id:
            log.debug(f"Item key not found in item_id list")
            await interaction.followup.send(
                f"Item '{item_name}' not found. Please use the exact in-game name.",
                ephemeral=True
            )
            return
        
        item_id = name_to_id[item_key]
        log.debug(f"Set item_id to {item_id}")

        command = [
            sys.executable,
            str(PRICE_CHECKER),
            "--type_id", str(item_id),
            "--market", str(market)
        ]

        log.debug(f"Running subprocess: {command}")
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=30, cwd=str(PROJECT_ROOT))
        log.debug(result.stdout)
        log.error(result.stderr)

        if result.returncode == 0:
            log.debug(f"Recieved code 0")
            price_text = result.stdout.strip()
            log.debug(f"Generated response as {price_text}")

        if result.returncode != 0:
            log.warning(f"Recieved code {result.returncode}")
            await interaction.followup.send(
                f"Market Summary failed for **{item_name}**.",
                ephemeral=True
            )
            return
        
        await interaction.followup.send(
            content=(
                price_text
            ),
        )
    try:
        await asyncio.wait_for(inner(), timeout=30)
    except asyncio.TimeoutError:
        await interaction.followup.send("Process took too long (30s timeout).", ephemeral=True)

@bot.tree.command(name="get_combined_graph", description="Send a price graph for the item with the Jita and GSF markets combined.")
@app_commands.describe(
    item_name="The exact name of the item you are looking for",
    days_history="How far back do you want to look in days? (Supports decimals)"
)
async def get_combined_graph(
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
        
        type_name = await match_item_name(item_id)
        filepath, display_days, resolved_type_name = await generate_combined_graph(item_id, days_history, type_name)

        
        if filepath is None:
            await interaction.followup.send(
                f"No data available for **{resolved_type_name}** in the past {days_history} days.",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            content=(
                f"Generated price graph for **{resolved_type_name}** over the last {display_days} days:"
            ),
            file=discord.File(filepath)
        )

        if not os.path.isfile(filepath):
            await interaction.followup.send(
                f" Expected graph file not found: `{filepath}`",
                ephemeral=True
            )
            return

    try:
        await asyncio.wait_for(inner(), timeout=45)
    except asyncio.TimeoutError:
        await interaction.followup.send("Graph generation took too long (45s timeout).", ephemeral=True)


bot.run(TOKEN)
