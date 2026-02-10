"""Videos cog for fetching recent team YouTube videos."""

import os

import discord
import httpx
import logfire
from discord.ext import commands


class Videos(commands.Cog):
    """Cog for team video commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = os.getenv("DBOT_API_URL", "http://localhost:8000/api/dbot")
        self.api_key = os.getenv("DBOT_AUTH_KEY", "")
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

    @discord.slash_command(name="videos", description="Show recent team YouTube videos")
    async def videos(self, ctx: discord.ApplicationContext):
        """Show the 5 most recent team YouTube videos."""
        await ctx.defer(ephemeral=True)

        guild = ctx.guild
        member = ctx.author

        if not guild or not isinstance(member, discord.Member):
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if not self._has_team_member_role(member):
            await ctx.respond("You need the Team Member role to use this command.", ephemeral=True)
            return

        headers = {
            "X-API-Key": self.api_key,
            "X-Guild-Id": str(guild.id),
            "X-Discord-User-Id": str(member.id),
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/recent_videos",
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    videos = data.get("videos", [])
                    team_feed_url = data.get("team_feed_url", "")

                    if not videos:
                        await ctx.respond("No team videos found yet.", ephemeral=True)
                        return

                    embed = discord.Embed(
                        title="Recent Team Videos",
                        color=discord.Color.red(),
                    )

                    for video in videos:
                        title = video.get("title", "Untitled")
                        url = video.get("url", "")
                        user_name = video.get("user_name", "Unknown")
                        published_at = video.get("published_at", "")

                        # Format date if available
                        date_str = ""
                        if published_at:
                            date_str = f" \u2022 {published_at[:10]}"

                        embed.add_field(
                            name=f"[{title} \u2197]({url})",
                            value=f"by {user_name}{date_str}",
                            inline=False,
                        )

                    if team_feed_url:
                        embed.add_field(
                            name="\u200b",
                            value=f"[View all on Team Feed \u2197]({team_feed_url})",
                            inline=False,
                        )

                    await ctx.respond(embed=embed, ephemeral=True)
                else:
                    await ctx.respond(
                        f"Failed to fetch videos. Server returned status {response.status_code}.",
                        ephemeral=True,
                    )

        except httpx.TimeoutException:
            await ctx.respond(
                "Request timed out. Please try again later.",
                ephemeral=True,
            )
        except httpx.RequestError as e:
            await ctx.respond(
                f"Failed to connect to the API: {e}",
                ephemeral=True,
            )

    async def cog_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Handle errors for commands in this cog."""
        if isinstance(error, commands.CheckFailure):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        else:
            logfire.error(
                "Command error in Videos cog",
                error=str(error),
                command=ctx.command.name if ctx.command else "unknown",
            )
            raise error


def setup(bot: commands.Bot):
    """Load the Videos cog."""
    bot.add_cog(Videos(bot))
