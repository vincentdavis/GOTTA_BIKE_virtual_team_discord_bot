"""Join The Coalition cog for new member onboarding."""

import os

import discord
import httpx
import logfire
from discord.ext import commands


class RegistrationButton(discord.ui.View):
    """View containing a button that links to the registration form."""

    def __init__(self, application_url: str):
        """Initialize the registration button.

        Args:
            application_url: The URL to the membership registration form.

        """
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Team Registration",
                style=discord.ButtonStyle.link,
                url=application_url,
            )
        )


class JoinCoalition(commands.Cog):
    """Cog for new member onboarding."""

    def __init__(self, bot: commands.Bot):
        """Initialize the cog.

        Args:
            bot: The Discord bot instance.

        """
        self.bot = bot
        self.api_url = os.getenv("DBOT_API_URL", "http://localhost:8000/api/dbot")
        self.api_key = os.getenv("DBOT_AUTH_KEY", "")
        self.guild_id = os.getenv("DISCORD_GUILD_ID", "")

    def _get_private_message(self) -> str:
        """Get the private message from server config.

        Returns:
            The configured private message, or a default message.

        """
        if hasattr(self.bot, "server_config") and self.bot.server_config.new_arrival_message_private:
            return self.bot.server_config.new_arrival_message_private
        return "Welcome to The Coalition! Please complete your team registration using the button below."

    def _format_message(self, message: str, member: discord.Member) -> str:
        """Format a message by replacing placeholders.

        Args:
            message: The message template with placeholders.
            member: The Discord member to use for placeholders.

        Returns:
            The formatted message with placeholders replaced.

        """
        server_name = member.guild.name if member.guild else "the server"
        # These are intentional placeholder strings, not f-strings
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
            "modal_form_data": {},  # Empty - user will fill out on web form
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
                        "Membership application created/retrieved via command",
                        member_id=member.id,
                        member_name=str(member),
                        application_id=result.get("id"),
                        already_exists=result.get("already_exists", False),
                    )
                    return result
                else:
                    logfire.error(
                        "Failed to create membership application",
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

    async def _send_registration_dm(self, member: discord.Member, application_url: str) -> bool:
        """Send a DM to the member with registration link.

        Args:
            member: The Discord member to DM.
            application_url: The URL to the registration form.

        Returns:
            True if DM was sent successfully, False otherwise.

        """
        private_msg = self._get_private_message()
        formatted_msg = self._format_message(private_msg, member)
        view = RegistrationButton(application_url)

        try:
            await member.send(formatted_msg, view=view)
            logfire.info(
                "Registration DM sent via command",
                member_id=member.id,
                member_name=str(member),
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
                "Failed to send registration DM",
                error=str(e),
                member_id=member.id,
            )
            return False

    @discord.slash_command(name="join_the_coalition", description="Apply to join The Coalition team")
    async def join_the_coalition(self, ctx: discord.ApplicationContext):
        """Start the application process to join The Coalition."""
        if not isinstance(ctx.author, discord.Member):
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        # Create or retrieve membership application
        api_result = await self._create_membership_application(ctx.author)

        if not api_result or not api_result.get("application_url"):
            await ctx.respond(
                "Sorry, there was an error creating your registration. Please try again later or contact the team.",
                ephemeral=True,
            )
            return

        application_url = api_result.get("application_url")

        # Get and format the private message
        private_msg = self._get_private_message()
        formatted_msg = self._format_message(private_msg, ctx.author)

        # Create the registration button view
        view = RegistrationButton(application_url)

        # Send ephemeral message (only the user sees it)
        await ctx.respond(formatted_msg, view=view, ephemeral=True)

        # Send DM with the same message
        dm_sent = await self._send_registration_dm(ctx.author, application_url)

        if not dm_sent:
            # If DM failed, send a follow-up ephemeral message
            await ctx.followup.send(
                "Note: I couldn't send you a DM. Please make sure your DMs are open, "
                "or use the button above to access your registration.",
                ephemeral=True,
            )

        logfire.info(
            "Join The Coalition command completed",
            member_id=ctx.author.id,
            member_name=str(ctx.author),
            application_url=application_url,
            dm_sent=dm_sent,
        )

    async def cog_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Handle errors for commands in this cog.

        Args:
            ctx: The application context.
            error: The exception that was raised.

        """
        if isinstance(error, commands.CheckFailure):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        else:
            logfire.error(
                "Command error in JoinCoalition cog",
                error=str(error),
                command=ctx.command.name if ctx.command else "unknown",
            )
            raise error


def setup(bot: commands.Bot):
    """Load the JoinCoalition cog.

    Args:
        bot: The Discord bot instance.

    """
    bot.add_cog(JoinCoalition(bot))
