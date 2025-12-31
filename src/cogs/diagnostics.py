"""Diagnostics cog for debug commands."""

import os

import discord
from discord.ext import commands


def is_debug_mode() -> bool:
    """Check if DEBUG mode is enabled."""
    return os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")


class Diagnostics(commands.Cog):
    """Cog for diagnostic commands (debug mode only)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.slash_command(name="diag", description="Show diagnostic information (debug mode only)")
    async def diag(self, ctx: discord.ApplicationContext):
        """Return diagnostic information about the user and guild."""
        if not is_debug_mode():
            await ctx.respond("This command is only available in debug mode.", ephemeral=True)
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

        response = (
            f"**Diagnostic Information**\n"
            f"```\n"
            f"Guild ID:          {guild.id if guild else 'N/A'}\n"
            f"Discord ID:        {member.id}\n"
            f"Discord Username:  {member.name}\n"
            f"Discord Nickname:  {member.nick if hasattr(member, 'nick') and member.nick else 'None'}\n"
            f"Has Roles:         {has_roles}\n"
            f"```\n"
            f"**Roles:**\n{roles_text}"
        )

        await ctx.respond(response, ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(Diagnostics(bot))
