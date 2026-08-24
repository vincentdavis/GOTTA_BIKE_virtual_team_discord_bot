"""Connect Zwift cog: links to the app's Zwift connection page."""

import os

import discord
import logfire
from discord.ext import commands

DEFAULT_CONNECT_URL = "https://app.coalitionracing.com/user/zauth/"


class ConnectZwift(commands.Cog):
    """Cog for pointing riders at the app's Connect to Zwift page."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # A plain link, so no API round-trip: the page is behind the app's own login and
        # handles both the connected and not-yet-connected cases itself.
        self.connect_url = os.getenv("APP_ZWIFT_CONNECT_URL", DEFAULT_CONNECT_URL)

    @discord.slash_command(name="connect_zwift", description="Get a link to connect your Zwift account")
    @discord.option("private", description="Only show the response to you", type=bool, default=True)
    async def connect_zwift(self, ctx: discord.ApplicationContext, private: bool):
        """Reply with a link to the app's Zwift connection page.

        Args:
            ctx: The command context.
            private: Whether to show the reply only to the caller (default yes).

        """
        embed = discord.Embed(
            title="Connect your Zwift account",
            description=(
                "Connecting lets the team app read your official Zwift racing profile "
                "— category, racing score, zFTP and zMAP — and is what squads "
                "check when they require a verified Zwift connection.\n\n"
                f"[Connect to Zwift]({self.connect_url})"
            ),
            color=discord.Color.orange(),
        )
        embed.set_footer(text="You will be asked to sign in to the team app first.")

        logfire.info(
            "Connect Zwift link requested",
            discord_user_id=str(ctx.author.id),
            guild_id=str(ctx.guild.id) if ctx.guild else None,
        )
        await ctx.respond(embed=embed, ephemeral=private)

    async def cog_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Handle errors for commands in this cog."""
        if isinstance(error, commands.CheckFailure):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        else:
            logfire.error(
                "Command error in ConnectZwift cog",
                error=str(error),
                command=ctx.command.name if ctx.command else "unknown",
            )
            raise error


def setup(bot: commands.Bot):
    """Load the ConnectZwift cog."""
    bot.add_cog(ConnectZwift(bot))
