"""In-channel roster cog for generating filtered roster links."""

import os

import discord
import httpx
import logfire
from discord.ext import commands


class InChannel(commands.Cog):
    """Cog for channel-based roster filtering commands."""

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

    @discord.slash_command(name="in_channel", description="Get roster link for members in this channel")
    async def in_channel(self, ctx: discord.ApplicationContext):
        """Generate a filtered roster link showing only members who can see this channel."""
        await ctx.defer(ephemeral=True)

        guild = ctx.guild
        member = ctx.author
        channel = ctx.channel

        if not guild or not isinstance(member, discord.Member):
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if not self._has_team_member_role(member):
            await ctx.respond("You need the Team Member role to use this command.", ephemeral=True)
            return

        # If used in a thread, resolve to the parent channel
        if isinstance(channel, discord.Thread):
            channel = channel.parent
            if channel is None:
                await ctx.respond("Could not resolve the parent channel for this thread.", ephemeral=True)
                return

        # Get members who can see this channel
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel)):
            await ctx.respond("This command can only be used in text, voice, or forum channels.", ephemeral=True)
            return

        # Get discord_ids of members who can view this channel
        channel_members = channel.members
        discord_ids = [str(m.id) for m in channel_members if not m.bot]

        if not discord_ids:
            await ctx.respond("No members found in this channel.", ephemeral=True)
            return

        headers = {
            "X-API-Key": self.api_key,
            "X-Guild-Id": str(guild.id),
            "X-Discord-User-Id": str(member.id),
        }

        payload = {
            "discord_ids": discord_ids,
            "channel_name": channel.name,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/roster_filter",
                    headers=headers,
                    json=payload,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    filter_url = data.get("url", "")
                    expires_in = data.get("expires_in_seconds", 300)
                    member_count = data.get("member_count", len(discord_ids))

                    await ctx.respond(
                        f"Here's your filtered roster link for **#{channel.name}**:\n\n"
                        f"{filter_url}\n\n"
                        f"Showing team members from {member_count} channel members.\n"
                        f"This link expires in {expires_in // 60} minutes.",
                        ephemeral=True,
                    )
                else:
                    await ctx.respond(
                        f"Failed to generate link. Server returned status {response.status_code}.",
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
                "Command error in InChannel cog",
                error=str(error),
                command=ctx.command.name if ctx.command else "unknown",
            )
            raise error


def setup(bot: commands.Bot):
    """Set up the InChannel cog."""
    bot.add_cog(InChannel(bot))
