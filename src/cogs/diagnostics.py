"""Diagnostics cog for debug commands."""

import os

import discord
import logfire
from discord.ext import commands


def is_debug_mode() -> bool:
    """Check if DEBUG mode is enabled."""
    return os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")


class Diagnostics(commands.Cog):
    """Cog for diagnostic commands (debug mode only)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Fallback to env var, but prefer server_config at runtime
        self._env_team_member_role_id = os.getenv("TEAM_MEMBER_ROLE_ID", "")

    @property
    def team_member_role_id(self) -> str:
        """Get team member role ID from server config or env fallback."""
        if hasattr(self.bot, "server_config") and self.bot.server_config.team_member_role_id:
            return self.bot.server_config.team_member_role_id
        return self._env_team_member_role_id

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

    @discord.slash_command(name="diag", description="Show diagnostic information (debug mode only)")
    async def diag(self, ctx: discord.ApplicationContext):
        """Return diagnostic information about the user and guild."""
        if not is_debug_mode():
            await ctx.respond("This command is only available in debug mode.", ephemeral=True)
            return

        if not isinstance(ctx.author, discord.Member) or not self._has_team_member_role(ctx.author):
            await ctx.respond("You need the Team Member role to use this command.", ephemeral=True)
            return

        member = ctx.author
        guild = ctx.guild

        # Build roles list
        roles_list = []
        for role in member.roles:
            if role.name != "@everyone":
                roles_list.append(f"- {role.name} ({role.id})")

        roles_text = "\n".join(roles_list) if roles_list else "No roles"
        has_roles = bool(roles_list)

        # Build config status section
        config_status = "Not loaded"
        config_values = "N/A"
        if hasattr(self.bot, "server_config") and self.bot.server_config:
            cfg = self.bot.server_config
            config_status = "Loaded from API" if cfg._loaded_from_api else "Loaded from ENV (fallback)"
            # Truncate long message fields for display
            public_msg = cfg.new_arrival_message_public
            public_display = (public_msg[:50] + "...") if public_msg and len(public_msg) > 50 else public_msg or "None"
            private_msg = cfg.new_arrival_message_private
            private_display = (
                (private_msg[:50] + "...") if private_msg and len(private_msg) > 50 else private_msg or "None"
            )

            config_lines = [
                f"  upgrade_channel:            {cfg.upgrade_channel or 'None'}",
                f"  new_arrivals_channel_id:    {cfg.new_arrivals_channel_id or 'None'}",
                f"  team_member_role_id:        {cfg.team_member_role_id or 'None'}",
                f"  race_ready_role_id:         {cfg.race_ready_role_id or 'None'}",
                f"  new_arrival_message_public: {public_display}",
                f"  new_arrival_message_private:{private_display}",
                f"  last_updated:               {cfg.last_updated or 'None'}",
            ]
            config_values = "\n".join(config_lines)

        response = (
            f"**Diagnostic Information**\n"
            f"```\n"
            f"Guild ID:          {guild.id if guild else 'N/A'}\n"
            f"Discord ID:        {member.id}\n"
            f"Discord Username:  {member.name}\n"
            f"Discord Nickname:  {member.nick if hasattr(member, 'nick') and member.nick else 'None'}\n"
            f"Has Roles:         {has_roles}\n"
            f"```\n"
            f"**Server Config:** {config_status}\n"
            f"```\n{config_values}\n```\n"
            f"**Roles:**\n{roles_text}"
        )

        await ctx.respond(response, ephemeral=True)

    async def cog_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Handle errors for commands in this cog."""
        if isinstance(error, commands.CheckFailure):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        else:
            logfire.error(
                "Command error in Diagnostics cog",
                error=str(error),
                command=ctx.command.name if ctx.command else "unknown",
            )
            raise error


def setup(bot: commands.Bot):
    bot.add_cog(Diagnostics(bot))
