"""Entry point for running the bot."""

import os

import logfire
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logfire for observability
logfire.configure(
    service_name="race-ready-zwift-bot",
    environment=os.getenv("LOGFIRE_ENVIRONMENT", "development"),
)

from src.bot import bot

# Load cogs
cogs = [
    "src.cogs.about",
    "src.cogs.race_ready_signup",
]

for cog in cogs:
    try:
        bot.load_extension(cog)
        print(f"Loaded: {cog}")
    except Exception as e:
        print(f"Failed to load {cog}: {e}")

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
