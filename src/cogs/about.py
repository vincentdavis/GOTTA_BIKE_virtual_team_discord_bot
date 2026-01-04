"""About cog with help command."""

import os

import discord
from discord.ext import commands


class About(commands.Cog):
    """Cog for informational commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.team_member_role_id = os.getenv("TEAM_MEMBER_ROLE_ID", "")

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
        await ctx.respond(
            "Racing on Zwift transcends mere exercise; it's a metaphysical confrontation "
            "between ego and algorithm — where watts become wisdom, suffering becomes synergy, "
            "and every virtual climb mirrors the uphill struggles of our digitized humanity."
        )


def setup(bot: commands.Bot):
    bot.add_cog(About(bot))
