"""Discord bot instance."""

import asyncio

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

# Ensure an event loop exists before creating the bot
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

bot = commands.Bot(intents=intents)
