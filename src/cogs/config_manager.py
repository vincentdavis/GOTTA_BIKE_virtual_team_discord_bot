"""Config manager cog for fetching configuration from the Django API."""

import os
from dataclasses import dataclass, field

import httpx
import logfire
from discord.ext import commands, tasks


@dataclass
class ServerConfig:
    """Configuration values fetched from the server.

    Stores configuration that can be updated at runtime via the Django admin.
    Falls back to environment variables if server fetch fails.
    """

    upgrade_channel: str | None = None
    new_arrivals_channel_id: str | None = None
    team_member_role_id: str | None = None
    race_ready_role_id: str | None = None
    new_arrival_message_public: str | None = None
    new_arrival_message_private: str | None = None
    send_new_arrival_dm: bool = True
    help_message: str | None = None
    last_updated: str | None = None
    _loaded_from_api: bool = field(default=False, repr=False)

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create config from environment variables as fallback.

        Returns:
            ServerConfig instance with values from environment.

        """
        return cls(
            upgrade_channel=os.getenv("UPGRADE_CHANNEL") or None,
            new_arrivals_channel_id=os.getenv("NEW_ARRIVALS_CHANNEL_ID") or None,
            team_member_role_id=os.getenv("TEAM_MEMBER_ROLE_ID") or None,
            race_ready_role_id=os.getenv("RACE_READY_ROLE_ID") or None,
            new_arrival_message_public=None,
            new_arrival_message_private=None,
            send_new_arrival_dm=True,
            help_message=None,
            _loaded_from_api=False,
        )

    @classmethod
    def from_api_response(cls, data: dict) -> "ServerConfig":
        """Create config from API response.

        Args:
            data: The API response dict.

        Returns:
            ServerConfig instance with values from API.

        """
        from datetime import datetime

        return cls(
            upgrade_channel=data.get("upgrade_channel"),
            new_arrivals_channel_id=data.get("new_arrivals_channel_id"),
            team_member_role_id=data.get("team_member_role_id"),
            race_ready_role_id=data.get("race_ready_role_id"),
            new_arrival_message_public=data.get("new_arrival_message_public"),
            new_arrival_message_private=data.get("new_arrival_message_private"),
            send_new_arrival_dm=data.get("send_new_arrival_dm", True),
            help_message=data.get("help_message"),
            last_updated=datetime.now().isoformat(),
            _loaded_from_api=True,
        )


class ConfigManager(commands.Cog):
    """Cog for managing bot configuration from the Django API.

    Fetches configuration on startup and periodically (every hour).
    Stores config in bot.server_config for access by other cogs.
    Falls back to environment variables if API is unavailable.
    """

    def __init__(self, bot: commands.Bot):
        """Initialize the ConfigManager cog.

        Args:
            bot: The Discord bot instance.

        """
        self.bot = bot
        self.api_url = os.getenv("DBOT_API_URL", "http://localhost:8000/api/dbot")
        self.api_key = os.getenv("DBOT_AUTH_KEY", "")
        self.guild_id = os.getenv("DISCORD_GUILD_ID", "")

        # Initialize with environment variable fallback
        self.bot.server_config = ServerConfig.from_env()

    def cog_unload(self):
        """Stop background tasks when cog is unloaded."""
        self.periodic_config_refresh.cancel()

    def _get_headers(self) -> dict:
        """Get headers for API requests.

        Returns:
            Headers dict for the API request.

        """
        return {
            "X-API-Key": self.api_key,
            "X-Guild-Id": self.guild_id,
            "X-Discord-User-Id": str(self.bot.user.id) if self.bot.user else "0",
        }

    async def _fetch_config(self) -> ServerConfig | None:
        """Fetch configuration from the Django API.

        Returns:
            ServerConfig instance if successful, None if failed.

        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/bot_config",
                    headers=self._get_headers(),
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    config = ServerConfig.from_api_response(data)
                    logfire.info(
                        "Fetched bot config from API",
                        new_arrivals_channel=config.new_arrivals_channel_id,
                        team_member_role=config.team_member_role_id,
                        race_ready_role=config.race_ready_role_id,
                    )
                    return config
                else:
                    logfire.warning(
                        "Failed to fetch bot config",
                        status_code=response.status_code,
                        response=response.text[:200],
                    )
                    return None

        except httpx.TimeoutException:
            logfire.warning("Bot config fetch timed out, using cached/env config")
            return None
        except httpx.RequestError as e:
            logfire.warning("Bot config fetch failed", error=str(e))
            return None

    async def refresh_config(self) -> bool:
        """Refresh configuration from the API.

        Updates bot.server_config if fetch is successful.
        Keeps existing config if fetch fails.

        Returns:
            True if config was updated, False otherwise.

        """
        new_config = await self._fetch_config()
        if new_config:
            self.bot.server_config = new_config
            return True
        return False

    @commands.Cog.listener()
    async def on_ready(self):
        """Fetch config when bot starts."""
        logfire.info("ConfigManager cog ready, fetching initial config...")

        # Fetch config on startup
        success = await self.refresh_config()
        if not success:
            logfire.warning("Using environment variable fallback for config")

        # Start periodic refresh task
        if not self.periodic_config_refresh.is_running():
            self.periodic_config_refresh.start()

    @tasks.loop(hours=1)
    async def periodic_config_refresh(self):
        """Periodically refresh configuration from the API."""
        logfire.info("Periodic config refresh...")
        await self.refresh_config()

    @periodic_config_refresh.before_loop
    async def before_periodic_refresh(self):
        """Wait until the bot is ready before starting periodic refresh."""
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot):
    """Set up the ConfigManager cog.

    Args:
        bot: The Discord bot instance.

    """
    bot.add_cog(ConfigManager(bot))
