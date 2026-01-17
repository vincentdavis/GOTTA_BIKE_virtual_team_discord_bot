"""Welcome cog for greeting new members."""

import os

import discord
import logfire
from discord.ext import commands

from src.cogs.join_coalition import JoinCoalitionModal


class JoinCoalitionButton(discord.ui.View):
    """View containing a button to open the join coalition modal."""

    def __init__(
        self,
        welcome_channel_id: str,
        api_url: str,
        api_key: str,
        guild_id: str,
    ):
        super().__init__(timeout=None)  # Persistent view (no timeout)
        self.welcome_channel_id = welcome_channel_id
        self.api_url = api_url
        self.api_key = api_key
        self.guild_id = guild_id

    @discord.ui.button(
        label="Join The Coalition",
        style=discord.ButtonStyle.green,
        custom_id="join_coalition_button",
    )
    async def join_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle button click to open the join modal."""
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button can only be used in a server.",
                ephemeral=True,
            )
            return

        user_nickname = interaction.user.nick or interaction.user.display_name

        modal = JoinCoalitionModal(
            user_nickname=user_nickname,
            welcome_channel_id=self.welcome_channel_id,
            api_url=self.api_url,
            api_key=self.api_key,
            guild_id=self.guild_id,
            title="Join The Coalition",
        )
        await interaction.response.send_modal(modal)


class Welcome(commands.Cog):
    """Cog for welcoming new members to the server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id = os.getenv("WELCOME_TEAM_CHANNEL", "")
        self.api_url = os.getenv("DBOT_API_URL", "http://localhost:8000/api/dbot")
        self.api_key = os.getenv("DBOT_AUTH_KEY", "")
        self.guild_id = os.getenv("DISCORD_GUILD_ID", "")

        # Register persistent view for button to work after bot restart
        self.bot.add_view(
            JoinCoalitionButton(
                welcome_channel_id=self.welcome_channel_id,
                api_url=self.api_url,
                api_key=self.api_key,
                guild_id=self.guild_id,
            )
        )

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
            "Please complete our membership application by typing `/join_the_coalition` right here "
            "or click the button below."
        )

        view = JoinCoalitionButton(
            welcome_channel_id=self.welcome_channel_id,
            api_url=self.api_url,
            api_key=self.api_key,
            guild_id=self.guild_id,
        )

        try:
            await channel.send(welcome_message, view=view)
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
