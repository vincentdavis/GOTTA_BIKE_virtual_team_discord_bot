"""Welcome cog for greeting new members."""

import os

import discord
import logfire
from discord.ext import commands


class Welcome(commands.Cog):
    """Cog for welcoming new members to the server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id = os.getenv("WELCOME_TEAM_CHANNEL", "")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send a welcome message when a new member joins.

        Args:
            member: The Discord member who joined.

        """
        if not self.welcome_channel_id:
            logfire.warning("WELCOME_TEAM_CHANNEL not configured, skipping welcome message")
            return

        channel = self.bot.get_channel(int(self.welcome_channel_id))
        if not channel:
            logfire.error(
                "Welcome channel not found",
                channel_id=self.welcome_channel_id,
            )
            return

        if not isinstance(channel, discord.TextChannel):
            logfire.error(
                "Welcome channel is not a text channel",
                channel_id=self.welcome_channel_id,
            )
            return

        welcome_message = (
            f"Hello {member.mention} Welcome to THE COALITION. Our membership team is here to help.\n"
            f"Please complete our membership application by typing `/join_the_coalition` right here."
        )

        try:
            await channel.send(welcome_message)
            logfire.info(
                "Welcome message sent",
                member_id=member.id,
                member_name=str(member),
                channel_id=self.welcome_channel_id,
            )
        except discord.Forbidden:
            logfire.error(
                "Bot lacks permission to send message in welcome channel",
                channel_id=self.welcome_channel_id,
            )
        except discord.HTTPException as e:
            logfire.error(
                "Failed to send welcome message",
                error=str(e),
                member_id=member.id,
            )


def setup(bot: commands.Bot):
    """Load the Welcome cog."""
    bot.add_cog(Welcome(bot))
