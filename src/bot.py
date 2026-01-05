"""Discord bot instance."""

import asyncio
import os

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required to access full guild member list

# Ensure an event loop exists before creating the bot
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Use debug_guilds for instant command sync to the configured guild
# Global commands can take up to an hour to propagate
guild_id = os.getenv("DISCORD_GUILD_ID")
debug_guilds = [int(guild_id)] if guild_id else None

bot = commands.Bot(intents=intents, debug_guilds=debug_guilds)
