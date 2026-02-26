"""Audio channel cog for finding companion voice channels."""

import discord
import logfire
from discord.ext import commands


class AudioChannel(commands.Cog):
    """Cog for finding the audio companion channel for the current text channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.slash_command(name="audio_channel", description="Get a link to this channel's audio channel")
    async def audio_channel(self, ctx: discord.ApplicationContext):
        """Find and link the audio companion channel for the current channel."""
        if not ctx.guild or not ctx.channel or not hasattr(ctx.channel, "name"):
            await ctx.respond("No matching audio channel was found.", ephemeral=True)
            return

        audio_name = f"{ctx.channel.name}-audio".lower()
        for channel in ctx.guild.channels:
            if channel.name.lower() == audio_name:
                await ctx.respond(channel.mention, ephemeral=True)
                return

        await ctx.respond("No matching audio channel was found.", ephemeral=True)

    async def cog_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Handle errors for commands in this cog."""
        if isinstance(error, commands.CheckFailure):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        else:
            logfire.error(
                "Command error in AudioChannel cog",
                error=str(error),
                command=ctx.command.name if ctx.command else "unknown",
            )
            raise error


def setup(bot: commands.Bot):
    bot.add_cog(AudioChannel(bot))
