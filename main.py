"""Race Ready discord bot
"""

import os

import logfire
from dotenv import load_dotenv

load_dotenv()

# Configure logfire for observability
# LOGFIRE_TOKEN is required in production; if not set, disable sending to logfire
logfire_token = os.getenv("LOGFIRE_TOKEN")
logfire.configure(
    service_name="race-ready-zwift-bot",
    environment=os.getenv("LOGFIRE_ENVIRONMENT", "development"),
    token=logfire_token,
    send_to_logfire="if-token-present",
)

TOKEN = os.getenv("DISCORD_TOKEN")

# Import bot instance from src.bot
from src.bot import bot  # noqa: E402

# Load cogs
COGS = [
    "src.cogs.about",
    "src.cogs.diagnostics",
    "src.cogs.team_links",
    "src.cogs.role_sync",
    "src.cogs.zwiftpower",
]


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    print(f"Connected to {len(bot.guilds)} guild(s):")
    for guild in bot.guilds:
        print(f"  - {guild.name} (ID: {guild.id})")
    print(f"Registered commands: {[cmd.name for cmd in bot.pending_application_commands]}")


def main():
    for cog in COGS:
        try:
            bot.load_extension(cog)
            print(f"Loaded cog: {cog}")
        except Exception as e:
            print(f"Failed to load cog {cog}: {e}")

    bot.run(TOKEN)


if __name__ == "__main__":
    main()
