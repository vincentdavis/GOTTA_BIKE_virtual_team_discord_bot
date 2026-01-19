"""Welcome cog for greeting new members."""

import os

import discord
import httpx
import logfire
from discord.ext import commands

from src.cogs.join_coalition import RegistrationButton

# Default public welcome message used when config is not set
DEFAULT_PUBLIC_MESSAGE = (
    "Hello {member} Welcome to THE COALITION. Our membership team is here to help.\n"
    "Please complete our membership registration by clicking the button below "
    "or typing `/join_the_coalition`."
)

# Default private message used when config is not set
DEFAULT_PRIVATE_MESSAGE = (
    "Welcome to The Coalition! Please complete your team registration using the button below."
)


class JoinButton(discord.ui.View):
    """Persistent button that triggers the registration flow."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        guild_id: str,
        bot: commands.Bot | None = None,
    ):
        """Initialize the join button view.

        Args:
            api_url: The API URL for creating membership applications.
            api_key: The API authentication key.
            guild_id: The Discord guild ID.
            bot: The bot instance for accessing server config.

        """
        super().__init__(timeout=None)  # Persistent view
        self.api_url = api_url
        self.api_key = api_key
        self.guild_id = guild_id
        self.bot = bot

    def _get_private_message(self) -> str:
        """Get the private message from server config or default.

        Returns:
            The configured private message or a default message.

        """
        if self.bot and hasattr(self.bot, "server_config") and self.bot.server_config.new_arrival_message_private:
            return self.bot.server_config.new_arrival_message_private
        return DEFAULT_PRIVATE_MESSAGE

    def _format_message(self, message: str, member: discord.Member) -> str:
        """Format a message by replacing placeholders.

        Args:
            message: The message template with placeholders.
            member: The Discord member to use for placeholders.

        Returns:
            The formatted message with placeholders replaced.

        """
        server_name = member.guild.name if member.guild else "the server"
        member_placeholder = "{member}"  # noqa: RUF027
        server_placeholder = "{server}"
        return message.replace(member_placeholder, member.display_name).replace(server_placeholder, server_name)

    async def _create_membership_application(self, member: discord.Member) -> dict | None:
        """Create or retrieve a membership application for the member via API.

        Args:
            member: The Discord member.

        Returns:
            API response dict with application_url, or None if failed.

        """
        headers = {
            "X-API-Key": self.api_key,
            "X-Guild-Id": self.guild_id,
            "X-Discord-User-Id": str(member.id),
        }

        payload = {
            "discord_id": str(member.id),
            "discord_username": member.name,
            "server_nickname": member.nick or member.display_name,
            "avatar_url": member.display_avatar.url if member.display_avatar else "",
            "guild_avatar_url": member.guild_avatar.url if member.guild_avatar else "",
            "discord_user_data": {
                "id": str(member.id),
                "name": member.name,
                "display_name": member.display_name,
                "discriminator": member.discriminator,
                "bot": member.bot,
                "created_at": member.created_at.isoformat() if member.created_at else None,
            },
            "discord_member_data": {
                "id": str(member.id),
                "nick": member.nick,
                "display_name": member.display_name,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                "roles": [{"id": str(r.id), "name": r.name} for r in member.roles],
            },
            "modal_form_data": {},
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/membership_application",
                    json=payload,
                    headers=headers,
                    timeout=15.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    logfire.info(
                        "Membership application created via welcome button",
                        member_id=member.id,
                        member_name=str(member),
                        application_id=result.get("id"),
                        already_exists=result.get("already_exists", False),
                    )
                    return result
                else:
                    logfire.error(
                        "Failed to create membership application via welcome button",
                        member_id=member.id,
                        status_code=response.status_code,
                        response=response.text,
                    )
                    return None

        except httpx.TimeoutException:
            logfire.error("Membership application API request timed out (welcome button)", member_id=member.id)
            return None
        except httpx.RequestError as e:
            logfire.error(
                "Membership application API request failed (welcome button)",
                member_id=member.id,
                error=str(e),
            )
            return None

    @discord.ui.button(
        label="Join The Coalition",
        style=discord.ButtonStyle.green,
        custom_id="welcome_join_button",
    )
    async def join_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle button click to create registration and show ephemeral response.

        Args:
            button: The button that was clicked.
            interaction: The interaction from the button click.

        """
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button can only be used in a server.",
                ephemeral=True,
            )
            return

        # Create or retrieve membership application
        api_result = await self._create_membership_application(interaction.user)

        if not api_result or not api_result.get("application_url"):
            await interaction.response.send_message(
                "Sorry, there was an error creating your registration. "
                "Please try `/join_the_coalition` or contact the team.",
                ephemeral=True,
            )
            return

        application_url = api_result.get("application_url")

        # Get and format the private message
        private_msg = self._get_private_message()
        formatted_msg = self._format_message(private_msg, interaction.user)

        # Create the registration link button
        view = RegistrationButton(application_url)

        # Send ephemeral response with registration link
        await interaction.response.send_message(formatted_msg, view=view, ephemeral=True)

        logfire.info(
            "Welcome join button clicked",
            member_id=interaction.user.id,
            member_name=str(interaction.user),
            application_url=application_url,
        )


class Welcome(commands.Cog):
    """Cog for welcoming new members to the server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Fallback to env vars, but prefer server_config at runtime
        self._env_welcome_channel_id = os.getenv("NEW_ARRIVALS_CHANNEL_ID", "")
        self.api_url = os.getenv("DBOT_API_URL", "http://localhost:8000/api/dbot")
        self.api_key = os.getenv("DBOT_AUTH_KEY", "")
        self.guild_id = os.getenv("DISCORD_GUILD_ID", "")
        self._view_registered = False

    @property
    def welcome_channel_id(self) -> str:
        """Get welcome channel ID from server config or env fallback."""
        if hasattr(self.bot, "server_config") and self.bot.server_config.new_arrivals_channel_id:
            return self.bot.server_config.new_arrivals_channel_id
        return self._env_welcome_channel_id

    def _format_message(self, message: str, member: discord.Member, use_mention: bool = True) -> str:
        """Format a message by replacing placeholders.

        Args:
            message: The message template with placeholders.
            member: The Discord member to use for placeholders.
            use_mention: If True, use member.mention for {member}; otherwise use display_name.

        Returns:
            The formatted message with placeholders replaced.

        """
        member_str = member.mention if use_mention else member.display_name
        server_name = member.guild.name if member.guild else "the server"
        # These are intentional placeholder strings, not f-strings
        member_placeholder = "{member}"  # noqa: RUF027
        server_placeholder = "{server}"
        return message.replace(member_placeholder, member_str).replace(server_placeholder, server_name)

    def _get_public_message(self) -> str:
        """Get the public welcome message from config or default.

        Returns:
            The configured public message or the default message.

        """
        if hasattr(self.bot, "server_config") and self.bot.server_config.new_arrival_message_public:
            return self.bot.server_config.new_arrival_message_public
        return DEFAULT_PUBLIC_MESSAGE

    def _get_private_message(self) -> str | None:
        """Get the private DM message from config, or None if not configured.

        Returns:
            The configured private message, or None if not set.

        """
        if hasattr(self.bot, "server_config") and self.bot.server_config.new_arrival_message_private:
            return self.bot.server_config.new_arrival_message_private
        return None

    async def _create_membership_application(self, member: discord.Member) -> dict | None:
        """Create a membership application for the new member via API.

        Args:
            member: The Discord member who joined.

        Returns:
            API response dict with application_url, or None if failed.

        """
        headers = {
            "X-API-Key": self.api_key,
            "X-Guild-Id": self.guild_id,
            "X-Discord-User-Id": str(member.id),
        }

        payload = {
            "discord_id": str(member.id),
            "discord_username": member.name,
            "server_nickname": member.nick or member.display_name,
            "avatar_url": member.display_avatar.url if member.display_avatar else "",
            "guild_avatar_url": member.guild_avatar.url if member.guild_avatar else "",
            "discord_user_data": {
                "id": str(member.id),
                "name": member.name,
                "display_name": member.display_name,
                "discriminator": member.discriminator,
                "bot": member.bot,
                "created_at": member.created_at.isoformat() if member.created_at else None,
            },
            "discord_member_data": {
                "id": str(member.id),
                "nick": member.nick,
                "display_name": member.display_name,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                "roles": [{"id": str(r.id), "name": r.name} for r in member.roles],
            },
            "modal_form_data": {},  # Empty - will be filled when user completes form
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/membership_application",
                    json=payload,
                    headers=headers,
                    timeout=15.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    logfire.info(
                        "Membership application created on member join",
                        member_id=member.id,
                        member_name=str(member),
                        application_id=result.get("id"),
                        already_exists=result.get("already_exists", False),
                    )
                    return result
                else:
                    logfire.error(
                        "Failed to create membership application on join",
                        member_id=member.id,
                        status_code=response.status_code,
                        response=response.text,
                    )
                    return None

        except httpx.TimeoutException:
            logfire.error(
                "Membership application API request timed out",
                member_id=member.id,
            )
            return None
        except httpx.RequestError as e:
            logfire.error(
                "Membership application API request failed",
                member_id=member.id,
                error=str(e),
            )
            return None

    async def _send_welcome_dm(self, member: discord.Member, application_url: str | None = None) -> bool:
        """Send a welcome DM to the member if configured.

        Args:
            member: The Discord member to DM.
            application_url: Optional URL to the member's registration form.

        Returns:
            True if DM was sent successfully, False otherwise.

        """
        private_msg = self._get_private_message()
        if not private_msg:
            return False

        formatted_msg = self._format_message(private_msg, member, use_mention=False)

        # Add registration link button if application_url is provided
        view = RegistrationButton(application_url) if application_url else None

        try:
            await member.send(formatted_msg, view=view)
            logfire.info(
                "Welcome DM sent",
                member_id=member.id,
                member_name=str(member),
                has_registration_link=application_url is not None,
            )
            return True
        except discord.Forbidden:
            logfire.warning(
                "Could not DM user - DMs disabled",
                member_id=member.id,
                member_name=str(member),
            )
            return False
        except discord.HTTPException as e:
            logfire.error(
                "Failed to send welcome DM",
                error=str(e),
                member_id=member.id,
            )
            return False

    def _create_join_button_view(self) -> JoinButton:
        """Create a JoinButton view with current config.

        Returns:
            A JoinButton view instance.

        """
        return JoinButton(
            api_url=self.api_url,
            api_key=self.api_key,
            guild_id=self.guild_id,
            bot=self.bot,
        )

    @commands.Cog.listener()
    async def on_ready(self):
        """Register persistent view when bot is ready."""
        if not self._view_registered:
            self.bot.add_view(self._create_join_button_view())
            self._view_registered = True
            logfire.info("Registered persistent JoinButton view for welcome messages")

    @discord.slash_command(name="test_welcome", description="Test the welcome message")
    async def test_welcome(self, ctx: discord.ApplicationContext):
        """Send a test welcome message mentioning the command user."""
        if not isinstance(ctx.author, discord.Member):
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if not self.welcome_channel_id:
            await ctx.respond("NEW_ARRIVALS_CHANNEL_ID not configured.", ephemeral=True)
            return

        channel = self.bot.get_channel(int(self.welcome_channel_id))
        if not channel or not isinstance(channel, discord.TextChannel):
            await ctx.respond("Welcome channel not found or not a text channel.", ephemeral=True)
            return

        # Create membership application to test the full flow
        application_url = None
        api_result = await self._create_membership_application(ctx.author)
        if api_result:
            application_url = api_result.get("application_url")

        # Get and format the public message
        public_msg = self._get_public_message()
        welcome_message = self._format_message(public_msg, ctx.author, use_mention=True)

        # Send public message with Join button
        view = self._create_join_button_view()
        await channel.send(welcome_message, view=view)

        # Also send test DM with registration link if configured
        dm_sent = await self._send_welcome_dm(ctx.author, application_url)

        if dm_sent:
            await ctx.respond("Test welcome message sent (public + DM with registration link)!", ephemeral=True)
        elif self._get_private_message():
            await ctx.respond("Test welcome message sent (public only - DM failed)!", ephemeral=True)
        else:
            await ctx.respond("Test welcome message sent (no private message configured)!", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send a welcome message when a new member joins.

        Creates a membership application, sends a public message in the welcome channel,
        and sends a private DM with a link to complete registration.

        Args:
            member: The Discord member who joined.

        """
        # Skip bots
        if member.bot:
            return

        # Create membership application first to get the registration URL
        application_url = None
        api_result = await self._create_membership_application(member)
        if api_result:
            application_url = api_result.get("application_url")

        if not self.welcome_channel_id:
            logfire.warning("NEW_ARRIVALS_CHANNEL_ID not configured, skipping welcome message")
            # Still try to send DM even if channel not configured
            await self._send_welcome_dm(member, application_url)
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

        # Get and format the public message
        public_msg = self._get_public_message()
        welcome_message = self._format_message(public_msg, member, use_mention=True)

        # Send public message with Join button
        view = self._create_join_button_view()
        try:
            await channel.send(welcome_message, view=view)
            logfire.info(
                "Public welcome message sent",
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

        # Send private DM with registration link if configured and enabled
        if hasattr(self.bot, "server_config") and self.bot.server_config.send_new_arrival_dm:
            await self._send_welcome_dm(member, application_url)


def setup(bot: commands.Bot):
    """Load the Welcome cog."""
    bot.add_cog(Welcome(bot))
