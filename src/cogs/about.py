"""About cog with help command."""

import os

import discord
import logfire
from discord.ext import commands


class About(commands.Cog):
    """Cog for informational commands."""

    # Default help message if not configured via API
    DEFAULT_HELP_MESSAGE = (
        "Racing on Zwift transcends mere exercise; it's a metaphysical confrontation "
        "between ego and algorithm — where watts become wisdom, suffering becomes synergy, "
        "and every virtual climb mirrors the uphill struggles of our digitized humanity."
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Fallback to env var, but prefer server_config at runtime
        self._env_team_member_role_id = os.getenv("TEAM_MEMBER_ROLE_ID", "")
        self.app_login_url = os.getenv("APP_LOGIN_URL", "")

    @property
    def team_member_role_id(self) -> str:
        """Get team member role ID from server config or env fallback."""
        if hasattr(self.bot, "server_config") and self.bot.server_config.team_member_role_id:
            return self.bot.server_config.team_member_role_id
        return self._env_team_member_role_id

    @property
    def help_message(self) -> str:
        """Get help message from server config or default fallback."""
        if hasattr(self.bot, "server_config") and self.bot.server_config.help_message:
            return self.bot.server_config.help_message
        return self.DEFAULT_HELP_MESSAGE

    def _has_team_member_role(self, member: discord.Member) -> bool:
        """Check if member has the team_member role.

        Args:
            member: The Discord member to check.

        Returns:
            True if member has the role or no role is configured.

        """
        if not self.team_member_role_id:
            return True
        return any(str(role.id) == self.team_member_role_id for role in member.roles)

    @discord.slash_command(name="help", description="Get philosophical wisdom about Zwift racing")
    async def help(self, ctx: discord.ApplicationContext):
        """Return philosophical text about Zwift racing."""
        if not isinstance(ctx.author, discord.Member) or not self._has_team_member_role(ctx.author):
            await ctx.respond("You need the Team Member role to use this command.", ephemeral=True)
            return
        await ctx.respond(self.help_message, ephemeral=True)

    @discord.slash_command(name="create_account", description="Get the link to create a team account")
    async def create_account(self, ctx: discord.ApplicationContext):
        """Return the app login URL for creating an account."""
        if not self.app_login_url:
            await ctx.respond(
                "App login URL is not configured. Please contact an administrator.",
                ephemeral=True,
            )
            return

        await ctx.respond(
            f"Create your team account here:\n{self.app_login_url}",
            ephemeral=True,
        )

    async def cog_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Handle errors for commands in this cog."""
        if isinstance(error, commands.CheckFailure):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        else:
            logfire.error(
                "Command error in About cog",
                error=str(error),
                command=ctx.command.name if ctx.command else "unknown",
            )
            raise error


def setup(bot: commands.Bot):
    bot.add_cog(About(bot))
