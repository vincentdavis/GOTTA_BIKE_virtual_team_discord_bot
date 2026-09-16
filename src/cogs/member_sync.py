"""Member sync cog for syncing Discord guild members with the Django API.

Two ways member state reaches the platform:

- The full push (``/sync_members`` and the periodic loop) refreshes every member in the
  gateway cache. It never marks anybody as left -- the cache can be missing chunks after a
  restart, so the platform only lets its own paginated REST sync decide departures.
- The leave hook (``on_raw_member_remove``) reports a single departure as it happens, so
  the platform can end that rider's access without waiting for its scheduled sync.

A push is skipped while the gateway is disconnected or resuming: py-cord keeps the member
cache (and ``is_ready()``) through a reconnect, so a push then could list members who left
while the bot was not receiving events, and clear a departure the platform recorded meanwhile.

Logging here carries ids and status codes only, never usernames or display names: the
platform's privacy rule, and this data lands in the same Logfire organisation.
"""

import asyncio
import os
from datetime import UTC, datetime

import discord
import httpx
import logfire
from discord.ext import commands, tasks

# Default sync interval in hours (can be overridden via env var)
DEFAULT_SYNC_INTERVAL_HOURS = 6

# Leave hook: total attempts, and the pause before each retry (seconds). Only connection
# errors, timeouts and 5xx responses are retried -- a 4xx will not get better on its own.
# The platform's scheduled guild sync is the backstop for a leave that never gets through.
MEMBER_LEFT_MAX_ATTEMPTS = 3
MEMBER_LEFT_RETRY_DELAYS = (2.0, 5.0)
MEMBER_LEFT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

STALE_CACHE_REPLY = "The bot is reconnecting to Discord, so its member list may be out of date. Try again in a minute."


class MemberCacheNotCurrentError(RuntimeError):
    """The gateway is disconnected or resuming, so the member cache may list members who left."""


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
        # Sync interval from env var (in hours), default to 6 hours
        self.sync_interval_hours = int(os.getenv("MEMBER_SYNC_INTERVAL_HOURS", DEFAULT_SYNC_INTERVAL_HOURS))
        # Whether the member cache is known to be current: set by on_ready (a fresh session,
        # cache rebuilt) and on_resumed (Discord sends RESUMED only after replaying every
        # missed event), cleared by on_disconnect. py-cord's is_ready() cannot tell us this --
        # it stays True through a reconnect. Seeded from is_ready() for a cog loaded late.
        self._member_cache_current = bot.is_ready()

    def cog_unload(self):
        """Stop background tasks when cog is unloaded."""
        self.periodic_member_sync.cancel()

    def _bot_user_id(self) -> str | None:
        """Return the bot's own Discord user ID, or None before the gateway has logged in.

        Returns:
            The bot user's ID as a string, or None if the bot user is not known yet.

        """
        return str(self.bot.user.id) if self.bot.user else None

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
            "X-Discord-User-Id": user_id or self._bot_user_id() or "",
        }

    async def _sync_guild_members(self, guild: discord.Guild, user_id: str | None = None) -> dict | None:
        """Sync all members from a guild to the Django API.

        Args:
            guild: The Discord guild to sync members from.
            user_id: The user ID who triggered the sync (defaults to the bot user).

        Returns:
            API response dict or None if failed.

        Raises:
            MemberCacheNotCurrentError: The gateway is disconnected or resuming; nothing was sent.

        """
        # Checked here, next to the read with no await in between, so a disconnect cannot slip
        # in after the check. A stale cache can still list members who left while no events
        # were arriving, and the platform clears every departure stamped before observed_at.
        if not self._member_cache_current:
            logfire.warning("Skipped guild member push: gateway not current", guild_id=guild.id)
            raise MemberCacheNotCurrentError
        # When the member list was read. Taken before iterating the cache, with no await in
        # between, so every leave the cache already reflects happened before this moment; the
        # platform will not clear a departure stamped at or after it (a leave newer than the list).
        observed_at = datetime.now(UTC).isoformat()
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
                    json={"members": members_data, "observed_at": observed_at},
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
                        departures_evaluated=result.get("departures_evaluated"),
                    )
                    return result
                else:
                    # Status only: a validation error body can echo the usernames we sent.
                    logfire.error(
                        "Failed to sync guild members",
                        status_code=response.status_code,
                        guild_id=guild.id,
                    )
                    return None

        except httpx.TimeoutException:
            logfire.error("Guild member sync timed out")
            return None
        except httpx.RequestError as e:
            logfire.error("Guild member sync request failed", error=str(e))
            return None

    def _member_is_back(self, guild_id: int, discord_id: int) -> bool:
        """Whether a member reported as gone is in the guild's member cache again.

        py-cord drops the member from the cache before dispatching the remove event and adds
        them back on GUILD_MEMBER_ADD, so a hit here means they have rejoined since.

        Args:
            guild_id: The guild the member left.
            discord_id: The member's Discord user ID.

        Returns:
            True if the cached guild lists the member again; False otherwise, including when
            the guild is not cached.

        """
        guild = self.bot.get_guild(guild_id)
        return guild is not None and guild.get_member(discord_id) is not None

    async def _report_member_left(self, guild_id: int, discord_id: int, body: dict) -> dict | None:
        """Tell the platform that a member has left the configured guild.

        Retries connection errors, timeouts and 5xx responses, with a pause between
        attempts; a 4xx is final. The endpoint is idempotent (a repeat answers
        ``already_departed``), so retrying a request the platform may have handled is safe --
        unless the member has come back meanwhile: the platform stamps the departure when the
        request arrives, not when the leave happened, so a late retry would sign a rider out
        again after they rejoined and signed in. Each attempt therefore first checks the
        member cache and stops if the member is back.

        Args:
            guild_id: The guild the member left (the configured guild).
            discord_id: The departed member's Discord user ID.
            body: The optional profile fields (``username``, ``display_name``,
                ``avatar_hash``, ``is_bot``) the platform uses only to create a
                GuildMember row it does not have yet.

        Returns:
            The platform's response dict, or None if the leave was not reported (failed, or
            the member rejoined first).

        """
        url = f"{self.api_url}/member_left/{discord_id}"
        headers = self._get_headers()
        async with httpx.AsyncClient(timeout=MEMBER_LEFT_TIMEOUT) as client:
            for attempt in range(1, MEMBER_LEFT_MAX_ATTEMPTS + 1):
                if self._member_is_back(guild_id, discord_id):
                    logfire.info(
                        "Member rejoined before the leave was reported; not reporting it",
                        discord_id=str(discord_id),
                        guild_id=self.guild_id,
                        attempt=attempt,
                    )
                    return None
                try:
                    response = await client.post(url, json=body, headers=headers)
                except httpx.TransportError as e:
                    # Connection refused, DNS, timeouts, dropped connections -- worth another go.
                    logfire.warning(
                        "Member leave report failed to reach the platform",
                        discord_id=str(discord_id),
                        guild_id=self.guild_id,
                        attempt=attempt,
                        error_type=type(e).__name__,
                    )
                else:
                    if response.status_code == 200:
                        result = response.json()
                        logfire.info(
                            "Reported member leave",
                            discord_id=str(discord_id),
                            guild_id=self.guild_id,
                            attempt=attempt,
                            status=result.get("status"),
                            created=result.get("created"),
                            ticket_created=result.get("ticket_created"),
                        )
                        return result
                    if response.status_code < 500:
                        # Status only: the body is not ours to copy into the logs.
                        logfire.error(
                            "Platform refused member leave report",
                            discord_id=str(discord_id),
                            guild_id=self.guild_id,
                            attempt=attempt,
                            status_code=response.status_code,
                        )
                        return None
                    logfire.warning(
                        "Platform error on member leave report",
                        discord_id=str(discord_id),
                        guild_id=self.guild_id,
                        attempt=attempt,
                        status_code=response.status_code,
                    )

                if attempt < MEMBER_LEFT_MAX_ATTEMPTS:
                    await asyncio.sleep(MEMBER_LEFT_RETRY_DELAYS[min(attempt, len(MEMBER_LEFT_RETRY_DELAYS)) - 1])

        logfire.error(
            "Could not report member leave; the platform's scheduled guild sync will record it",
            discord_id=str(discord_id),
            guild_id=self.guild_id,
            attempts=MEMBER_LEFT_MAX_ATTEMPTS,
        )
        return None

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent):
        """Report a member leaving the configured guild to the platform straight away.

        The raw event fires whether or not the member was in the cache, and for a leave,
        a kick or a ban alike (Discord sends GUILD_MEMBER_REMOVE for each). It needs only
        the members intent, which ``src/bot.py`` already enables. Never raises: a leave
        that cannot be reported is logged, and the platform's scheduled sync catches it.

        Args:
            payload: The raw member-remove event.

        """
        try:
            if not self.guild_id or str(payload.guild_id) != self.guild_id:
                return

            user = payload.user
            if not self._bot_user_id():
                logfire.error(
                    "Cannot report member leave before the bot user is known",
                    discord_id=str(user.id),
                    guild_id=self.guild_id,
                )
                return

            body = {
                "username": user.name,
                "display_name": user.display_name or user.global_name or "",
                "avatar_hash": user.avatar.key if user.avatar else "",
                "is_bot": user.bot,
            }
            await self._report_member_left(payload.guild_id, user.id, body)
        except Exception as e:
            logfire.error(
                "Member leave hook failed",
                discord_id=str(getattr(payload.user, "id", "")),
                guild_id=str(payload.guild_id),
                error_type=type(e).__name__,
                error=str(e),
            )

    @discord.slash_command(
        name="sync_members",
        description="Sync all guild members to the database",
        default_member_permissions=discord.Permissions(administrator=True),
    )
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

        if not self._member_cache_current:
            await ctx.respond(STALE_CACHE_REPLY, ephemeral=True)
            return

        await ctx.respond(
            f"Starting member sync for {len(guild.members)} members. This may take a moment...",
            ephemeral=True,
        )

        try:
            result = await self._sync_guild_members(guild, str(ctx.author.id))
        except MemberCacheNotCurrentError:
            # The gateway dropped between the check above and the push.
            await ctx.edit(content=STALE_CACHE_REPLY)
            return

        if result:
            content = (
                f"Member sync complete!\n"
                f"- Created: {result.get('created', 0)}\n"
                f"- Updated: {result.get('updated', 0)}\n"
                f"- Rejoined: {result.get('rejoined', 0)}\n"
                f"- Left: {result.get('left', 0)}\n"
                f"- Linked to accounts: {result.get('linked', 0)}\n"
                f"- Total active: {result.get('total_active', 0)}"
            )
            if result.get("departures_evaluated") is False:
                content += (
                    "\n\nThis push does not mark departures, so Left is always 0 here. "
                    "Leaves are recorded by the bot's leave hook as they happen, "
                    "and by the platform's scheduled guild sync."
                )
            await ctx.edit(content=content)
        else:
            await ctx.edit(content="Member sync failed. Check bot logs for details.")

    @commands.Cog.listener()
    async def on_disconnect(self):
        """Pause member pushes: no events arrive until the gateway resumes or reconnects."""
        if self._member_cache_current:
            logfire.info("Gateway disconnected; member pushes paused", guild_id=self.guild_id)
        self._member_cache_current = False

    @commands.Cog.listener()
    async def on_resumed(self):
        """Resume member pushes: Discord replays every missed event before RESUMED."""
        if not self._member_cache_current:
            logfire.info("Gateway resumed; member pushes allowed again", guild_id=self.guild_id)
        self._member_cache_current = True

    @commands.Cog.listener()
    async def on_ready(self):
        """Start periodic member sync when bot is ready.

        Also marks the member cache current: READY clears py-cord's cache, and on_ready is
        dispatched once the guilds have been chunked again. Fires on every new session, not
        only the first.
        """
        self._member_cache_current = True
        logfire.info(
            "MemberSync cog ready",
            sync_interval_hours=self.sync_interval_hours,
        )

        # Start periodic sync task if not already running
        if not self.periodic_member_sync.is_running():
            # Update the task interval based on config
            self.periodic_member_sync.change_interval(hours=self.sync_interval_hours)
            self.periodic_member_sync.start()

    @tasks.loop(hours=DEFAULT_SYNC_INTERVAL_HOURS)
    async def periodic_member_sync(self):
        """Periodically sync all guild members to ensure consistency."""
        for guild in self.bot.guilds:
            if str(guild.id) == self.guild_id:
                logfire.info(
                    "Starting periodic guild member sync",
                    guild_id=guild.id,
                    member_count=len(guild.members),
                )
                try:
                    result = await self._sync_guild_members(guild)
                except MemberCacheNotCurrentError:
                    # Already logged; the next interval tries again. Must not raise: an
                    # exception out of a tasks.loop body stops the loop for good.
                    break
                if result:
                    logfire.info(
                        "Periodic member sync complete",
                        created=result.get("created", 0),
                        updated=result.get("updated", 0),
                        rejoined=result.get("rejoined", 0),
                        left=result.get("left", 0),
                        linked=result.get("linked", 0),
                        total_active=result.get("total_active", 0),
                    )
                else:
                    logfire.error("Periodic member sync failed")
                break

    @periodic_member_sync.before_loop
    async def before_periodic_member_sync(self):
        """Wait until the bot is ready before starting periodic sync."""
        await self.bot.wait_until_ready()

    async def cog_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Handle errors for commands in this cog.

        Args:
            ctx: The application context.
            error: The error that occurred.

        """
        if isinstance(error, commands.MissingPermissions):
            await ctx.respond(
                "You don't have permission to use this command. Administrator access required.",
                ephemeral=True,
            )
        elif isinstance(error, commands.CheckFailure):
            await ctx.respond(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
        else:
            logfire.error(
                "Command error in MemberSync cog",
                error=str(error),
                command=ctx.command.name if ctx.command else "unknown",
            )
            raise error


def setup(bot: commands.Bot):
    """Set up the MemberSync cog.

    Args:
        bot: The Discord bot instance.

    """
    bot.add_cog(MemberSync(bot))
