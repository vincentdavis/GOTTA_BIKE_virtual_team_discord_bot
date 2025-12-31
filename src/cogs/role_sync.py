"""Role sync cog for syncing Discord roles with the Django API."""

import os

import discord
import httpx
import logfire
from discord.ext import commands, tasks


class RoleSync(commands.Cog):
    """Cog for syncing Discord roles to the Django API."""

    def __init__(self, bot: commands.Bot):
        """Initialize the RoleSync cog.

        Args:
            bot: The Discord bot instance.

        """
        self.bot = bot
        self.api_url = os.getenv("DBOT_API_URL", "http://localhost:8000/api/dbot")
        self.api_key = os.getenv("DBOT_AUTH_KEY", "")
        self.guild_id = os.getenv("DISCORD_GUILD_ID", "")

    def cog_unload(self):
        """Stop background tasks when cog is unloaded."""
        self.periodic_role_sync.cancel()

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

    async def _sync_guild_roles(self, guild: discord.Guild) -> dict | None:
        """Sync all roles from a guild to the Django API.

        Args:
            guild: The Discord guild to sync roles from.

        Returns:
            API response dict or None if failed.

        """
        roles_data = [
            {
                "id": str(role.id),
                "name": role.name,
                "color": role.color.value,
                "position": role.position,
                "managed": role.managed,
                "mentionable": role.mentionable,
            }
            for role in guild.roles
        ]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sync_guild_roles",
                    json={"roles": roles_data},
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    logfire.info(
                        "Synced guild roles",
                        created=result.get("created"),
                        updated=result.get("updated"),
                        deleted=result.get("deleted"),
                    )
                    return result
                else:
                    logfire.error(
                        "Failed to sync guild roles",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    return None

        except httpx.TimeoutException:
            logfire.error("Guild role sync timed out")
            return None
        except httpx.RequestError as e:
            logfire.error("Guild role sync request failed", error=str(e))
            return None

    async def _sync_user_roles(self, member: discord.Member) -> dict | None:
        """Sync a member's roles to the Django API.

        Args:
            member: The Discord member to sync roles for.

        Returns:
            API response dict or None if failed.

        """
        role_ids = [str(role.id) for role in member.roles]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sync_user_roles/{member.id}",
                    json={"role_ids": role_ids},
                    headers=self._get_headers(str(member.id)),
                    timeout=10.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    logfire.info(
                        "Synced user roles",
                        member=member.display_name,
                        member_id=member.id,
                        roles_synced=result.get("roles_synced"),
                    )
                    return result
                elif response.status_code == 404:
                    # User not in database - this is normal for users without accounts
                    return None
                else:
                    logfire.error(
                        "Failed to sync user roles",
                        member_id=member.id,
                        status_code=response.status_code,
                    )
                    return None

        except httpx.TimeoutException:
            logfire.error("User role sync timed out", member_id=member.id)
            return None
        except httpx.RequestError as e:
            logfire.error("User role sync request failed", member_id=member.id, error=str(e))
            return None

    @commands.Cog.listener()
    async def on_ready(self):
        """Sync all guild roles when bot starts."""
        logfire.info("RoleSync cog ready, syncing guild roles...")

        for guild in self.bot.guilds:
            if str(guild.id) == self.guild_id:
                await self._sync_guild_roles(guild)
                break

        # Start periodic sync task
        if not self.periodic_role_sync.is_running():
            self.periodic_role_sync.start()

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Sync roles when a new role is created.

        Args:
            role: The newly created role.

        """
        if str(role.guild.id) == self.guild_id:
            logfire.info("Role created, syncing", role_name=role.name)
            await self._sync_guild_roles(role.guild)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Sync roles when a role is deleted.

        Args:
            role: The deleted role.

        """
        if str(role.guild.id) == self.guild_id:
            logfire.info("Role deleted, syncing", role_name=role.name)
            await self._sync_guild_roles(role.guild)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Sync roles when a role is updated.

        Args:
            before: The role before the update.
            after: The role after the update.

        """
        if str(after.guild.id) != self.guild_id:
            return
        # Only sync if name, color, or position changed
        if before.name != after.name or before.color != after.color or before.position != after.position:
            logfire.info("Role updated, syncing", role_name=after.name)
            await self._sync_guild_roles(after.guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Sync user roles when a member's roles change.

        Args:
            before: The member before the update.
            after: The member after the update.

        """
        if str(after.guild.id) != self.guild_id:
            return

        # Check if roles changed
        if set(before.roles) != set(after.roles):
            logfire.info("Member roles changed, syncing", member=after.display_name)
            await self._sync_user_roles(after)

    @tasks.loop(hours=1)
    async def periodic_role_sync(self):
        """Periodically sync all guild roles to ensure consistency."""
        for guild in self.bot.guilds:
            if str(guild.id) == self.guild_id:
                logfire.info("Periodic guild role sync...")
                await self._sync_guild_roles(guild)
                break

    @periodic_role_sync.before_loop
    async def before_periodic_sync(self):
        """Wait until the bot is ready before starting periodic sync."""
        await self.bot.wait_until_ready()

    @discord.slash_command(name="sync_roles", description="Manually sync all guild roles to the database")
    @commands.has_permissions(administrator=True)
    async def sync_roles_command(self, ctx: discord.ApplicationContext):
        """Manually trigger a role sync (admin only)."""
        await ctx.defer(ephemeral=True)

        guild = ctx.guild
        if not guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if str(guild.id) != self.guild_id:
            await ctx.respond("This command can only be used in the configured guild.", ephemeral=True)
            return

        result = await self._sync_guild_roles(guild)

        if result:
            await ctx.respond(
                f"Role sync complete!\n"
                f"- Created: {result.get('created', 0)}\n"
                f"- Updated: {result.get('updated', 0)}\n"
                f"- Deleted: {result.get('deleted', 0)}\n"
                f"- Total: {result.get('total', 0)}",
                ephemeral=True,
            )
        else:
            await ctx.respond("Role sync failed. Check bot logs for details.", ephemeral=True)

    @discord.slash_command(name="sync_my_roles", description="Sync your roles to the team database")
    async def sync_my_roles_command(self, ctx: discord.ApplicationContext):
        """Allow a user to manually sync their own roles."""
        await ctx.defer(ephemeral=True)

        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if str(ctx.guild.id) != self.guild_id:
            await ctx.respond("This command can only be used in the configured guild.", ephemeral=True)
            return

        result = await self._sync_user_roles(ctx.author)

        if result:
            role_names = list(result.get("roles", {}).values())
            await ctx.respond(
                f"Your roles have been synced!\n"
                f"Roles: {', '.join(role_names[:10])}{'...' if len(role_names) > 10 else ''}",
                ephemeral=True,
            )
        else:
            await ctx.respond(
                "Could not sync your roles. Make sure you have an account on the team website.",
                ephemeral=True,
            )


def setup(bot: commands.Bot):
    """Set up the RoleSync cog.

    Args:
        bot: The Discord bot instance.

    """
    bot.add_cog(RoleSync(bot))
