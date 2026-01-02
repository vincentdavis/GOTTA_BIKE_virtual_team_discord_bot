"""Member sync cog for syncing Discord guild members with the Django API."""

import os

import discord
import httpx
import logfire
from discord.ext import commands


class MemberSync(commands.Cog):
    """Cog for syncing Discord guild members to the Django API."""

    def __init__(self, bot: commands.Bot):
        """Initialize the MemberSync cog.

        Args:
            bot: The Discord bot instance.

        """
        self.bot = bot
        self.api_url = os.getenv("DBOT_API_URL", "http://localhost:8000/api/dbot")
        self.api_key = os.getenv("DBOT_AUTH_KEY", "")
        self.guild_id = os.getenv("DISCORD_GUILD_ID", "")

    def _get_headers(self, user_id: str | None = None) -> dict:
        """Get headers for API requests.

        Args:
            user_id: Discord user ID for the request (defaults to bot user).

        Returns:
            Headers dict for the API request.

        """
        return {
            "X-API-Key": self.api_key,
            "X-Guild-Id": self.guild_id,
            "X-Discord-User-Id": user_id or str(self.bot.user.id),
        }

    async def _sync_guild_members(self, guild: discord.Guild, user_id: str) -> dict | None:
        """Sync all members from a guild to the Django API.

        Args:
            guild: The Discord guild to sync members from.
            user_id: The user ID who triggered the sync.

        Returns:
            API response dict or None if failed.

        """
        members_data = []
        for member in guild.members:
            avatar_hash = ""
            if member.avatar:
                avatar_hash = member.avatar.key

            members_data.append({
                "discord_id": str(member.id),
                "username": member.name,
                "display_name": member.display_name or "",
                "nickname": member.nick or "",
                "avatar_hash": avatar_hash,
                "roles": [str(role.id) for role in member.roles],
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                "is_bot": member.bot,
            })

        logfire.info(
            "Syncing guild members",
            member_count=len(members_data),
            guild_id=guild.id,
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sync_guild_members",
                    json={"members": members_data},
                    headers=self._get_headers(user_id),
                    timeout=60.0,  # Longer timeout for large guilds
                )

                if response.status_code == 200:
                    result = response.json()
                    logfire.info(
                        "Synced guild members",
                        created=result.get("created"),
                        updated=result.get("updated"),
                        rejoined=result.get("rejoined"),
                        left=result.get("left"),
                        linked=result.get("linked"),
                        total_active=result.get("total_active"),
                    )
                    return result
                else:
                    logfire.error(
                        "Failed to sync guild members",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    return None

        except httpx.TimeoutException:
            logfire.error("Guild member sync timed out")
            return None
        except httpx.RequestError as e:
            logfire.error("Guild member sync request failed", error=str(e))
            return None

    @discord.slash_command(name="sync_members", description="Sync all guild members to the database")
    @commands.has_permissions(administrator=True)
    async def sync_members_command(self, ctx: discord.ApplicationContext):
        """Sync all guild members to Django database (admin only).

        Args:
            ctx: The application context.

        """
        await ctx.defer(ephemeral=True)

        guild = ctx.guild
        if not guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if str(guild.id) != self.guild_id:
            await ctx.respond("This command can only be used in the configured guild.", ephemeral=True)
            return

        await ctx.respond(
            f"Starting member sync for {len(guild.members)} members. This may take a moment...",
            ephemeral=True,
        )

        result = await self._sync_guild_members(guild, str(ctx.author.id))

        if result:
            await ctx.edit(
                content=(
                    f"Member sync complete!\n"
                    f"- Created: {result.get('created', 0)}\n"
                    f"- Updated: {result.get('updated', 0)}\n"
                    f"- Rejoined: {result.get('rejoined', 0)}\n"
                    f"- Left: {result.get('left', 0)}\n"
                    f"- Linked to accounts: {result.get('linked', 0)}\n"
                    f"- Total active: {result.get('total_active', 0)}"
                ),
            )
        else:
            await ctx.edit(content="Member sync failed. Check bot logs for details.")


def setup(bot: commands.Bot):
    """Set up the MemberSync cog.

    Args:
        bot: The Discord bot instance.

    """
    bot.add_cog(MemberSync(bot))
