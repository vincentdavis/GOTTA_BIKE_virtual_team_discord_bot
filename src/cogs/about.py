"""About cog with help command."""

import discord
from discord.ext import commands


class About(commands.Cog):
    """Cog for informational commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.slash_command(name="help", description="Get philosophical wisdom about Zwift racing")
    async def help(self, ctx: discord.ApplicationContext):
        """Return philosophical text about Zwift racing."""
        await ctx.respond(
            "Racing on Zwift transcends mere exercise; it's a metaphysical confrontation "
            "between ego and algorithm — where watts become wisdom, suffering becomes synergy, "
            "and every virtual climb mirrors the uphill struggles of our digitized humanity."
        )


def setup(bot: commands.Bot):
    bot.add_cog(About(bot))
