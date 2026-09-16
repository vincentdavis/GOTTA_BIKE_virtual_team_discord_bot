# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discord bot for The Coalition Zwift racing team. Built with py-cord (discord.py fork) and communicates with a Django backend API for team management features.

## Commands

```bash
# Install dependencies
uv sync

# Run the bot
uv run main.py

# Lint and format
uv run ruff check .
uv run ruff format .

# Type checking
uv run ty check

# Docker
docker build -t coalition-bot .
docker run coalition-bot
```

## Architecture

**Entry Point:** `main.py` - Configures logfire, loads environment, registers cogs, and starts the bot.

**Bot Instance:** `src/bot.py` - Creates the Discord bot with the `message_content` and `members` intents enabled. `members` (Server Members Intent) is privileged and must also be switched on in the Discord Developer Portal; it gives the full member cache and the member join/update/remove events. In py-cord 2.8.1 it is the only intent `GUILD_MEMBER_REMOVE` (`on_member_remove` / `on_raw_member_remove`) needs.

**Cog System:** All Discord commands are organized as cogs in `src/cogs/`:
- `about.py` - `/help` command
- `audio_channel.py` - `/audio_channel` command (find companion voice channel)
- `connect_zwift.py` - `/connect_zwift` command (link to the app's Connect to Zwift page)
- `config_manager.py` - Fetches bot configuration from Django API (channel IDs, welcome messages, etc.)
- `diagnostics.py` - `/diag` debug command (DEBUG mode only)
- `in_channel.py` - `/in_channel` filtered roster command (creates link showing only channel members)
- `join_coalition.py` - `/join_the_coalition` membership application with multi-select form
- `member_sync.py` - Guild member state to Django: the full push (`/sync_members` and a periodic loop) and the leave hook (see Guild Member Sync below)
- `role_sync.py` - Syncs Discord roles to Django API (`/sync_roles`, `/sync_my_roles`)
- `team_links.py` - Magic link generation (`/team_links`)
- `welcome.py` - Sends welcome message to new members, `/test_welcome` command, handles Join button
- `zwiftpower.py` - ZwiftPower/ZwiftRacing profile commands (`/my_profile`, `/teammate_profile`)

### Command Permissions

| Command | Permission | Notes |
|---------|------------|-------|
| `/audio_channel` | Everyone | |
| `/connect_zwift` | Everyone | Plain link; the app's own login gates the page |
| `/help` | Team Member | |
| `/join_the_coalition` | Everyone | |
| `/team_links` | Team Member | |
| `/my_profile` | Team Member | |
| `/teammate_profile` | Team Member | |
| `/in_channel` | Team Member | |
| `/sync_my_roles` | Everyone | |
| `/sync_roles` | Administrator | |
| `/sync_members` | Administrator | |
| `/diag` | Team Member | Also requires `DEBUG=true` |
| `/test_welcome` | Everyone | |

**Permission Levels:**
- **Everyone**: No role required. If `TEAM_MEMBER_ROLE_ID` is not configured, Team Member commands also become available to everyone.
- **Team Member**: Requires the role specified by `TEAM_MEMBER_ROLE_ID` (configured via API or env var).
- **Administrator**: Requires Discord administrator permission (`@commands.has_permissions(administrator=True)`).

**Channel Permissions:**
Users must have the "Use Application Commands" permission in the channel to see and use slash commands. This is commonly disabled in welcome/arrivals channels - ensure it's enabled for @everyone if new members need to use commands like `/join_the_coalition`.

### Join Coalition Form Options

The `/join_the_coalition` command collects:
- **Reasons for joining:** Virtual Racing, Fitness and Training, Community
- **Platforms:** Zwift, Rouvy, MyWhoosh, TrainingPeaks Virtual, Other
- **Race series interest:** ZRL, TTT, ClubLadder, FRR, Women's Racing, Other

**API Communication:** Cogs authenticate to the Django backend using headers:
- `X-API-Key`: From `DBOT_AUTH_KEY` env var
- `X-Guild-Id`: From `DISCORD_GUILD_ID` env var
- `X-Discord-User-Id`: Requesting user's Discord ID — the bot's own user ID for calls no person triggered (periodic loops, event listeners). The platform refuses an empty value

### Guild Member Sync (`src/cogs/member_sync.py`)

Two paths, each matching an endpoint on the platform:

- **Full push** — `POST {DBOT_API_URL}/sync_guild_members` with `{"members": [...], "observed_at": "<ISO-8601 UTC>"}`, sent by `/sync_members` and every `MEMBER_SYNC_INTERVAL_HOURS` (default 6). `observed_at` is taken just before `guild.members` is read, with no `await` in between, so the platform can refuse to clear a departure stamped at or after it (a leave newer than the list). The push **never marks anyone as left** — the gateway cache can be missing chunks after a restart, so the platform only lets its own paginated REST sync decide departures. Its response carries `departures_evaluated: false`, and `/sync_members` then says so under the counts, because "Left: 0" is expected there. **No push while the gateway is not current**: py-cord keeps the member cache, and `is_ready()` stays True, through a disconnect, so a push then would list members who left while no events arrived, and clear any departure the platform recorded meanwhile. The cog tracks `_member_cache_current`. `on_disconnect` clears it. `on_resumed` sets it, because Discord replays every missed event before RESUMED, and so does `on_ready`, because READY clears the cache and `on_ready` follows the re-chunk. While the flag is clear, the periodic push is skipped (`MemberCacheNotCurrentError`, caught in the loop, since an exception would stop the `tasks.loop`) and `/sync_members` replies "reconnecting". The flag is checked inside `_sync_guild_members` with no `await` before the read. One residue remains: a connection that dies silently is only noticed after `heartbeat_timeout` (60s) without a gateway message.
- **Leave hook** — `on_raw_member_remove` posts `POST {DBOT_API_URL}/member_left/{discord_id}` as soon as someone leaves the `DISCORD_GUILD_ID` guild (other guilds, and an unset guild ID, are ignored). The raw event is used because it fires even when the member was not cached; it also fires for kicks and bans, which are not told apart. The optional body `{username, display_name, avatar_hash, is_bot}` is only used by the platform to create a `GuildMember` row it does not have. Connection errors, timeouts and 5xx are retried (3 attempts in all, pausing 2s then 5s); a 4xx is final. The endpoint is idempotent (`status` is `departed` or `already_departed`), so a retry is safe, **except after a rejoin**: the platform stamps the departure when the request arrives, and a Discord login clears the stamp, so a late retry would sign a rejoined rider out again. So each attempt first checks `guild.get_member(id)` and stops if the member is back. py-cord removes the member from the cache before dispatching the remove event and adds them back on `GUILD_MEMBER_ADD`. The listener never raises: a leave that never gets through is logged as an error, and the platform's scheduled guild sync records it later.
- **Logging** — ids and status codes only (`discord_id`, `guild_id`, `status_code`), never usernames, display names or response bodies (a validation error can echo what was sent). This is the platform's privacy rule, and the bot's traces land in the same Logfire organisation.

## Discord Components V2 (Modals with Select Menus)

This project uses py-cord 2.7+ which supports Discord's **Components V2** system. This allows select menus, file uploads, and other components inside modals (not just text inputs).

### Key Classes

- `discord.ui.DesignerModal` - Use instead of `discord.ui.Modal` for Components V2 features
- `discord.ui.Label` - Wrapper that adds a label and description to components in modals
- `discord.ui.TextDisplay` - Display text in modals (doesn't need Label wrapper)

### Supported Components in Modals (via Label wrapper)

- `discord.ui.InputText` - Text input fields
- `discord.ui.Select` - Single or multi-select dropdowns
- `discord.ui.FileUpload` - File upload fields

### Example Usage

```python
class MyModal(discord.ui.DesignerModal):
    def __init__(self, *args, **kwargs):
        # Text input wrapped in Label
        name_input = discord.ui.Label(
            "What is your name?",
            discord.ui.InputText(placeholder="Enter name", required=True),
        )

        # Select menu wrapped in Label (supports multi-select!)
        color_select = discord.ui.Label(
            "Favorite colors?",
            discord.ui.Select(
                placeholder="Select colors",
                min_values=1,
                max_values=3,
                options=[
                    discord.SelectOption(label="Red", value="red"),
                    discord.SelectOption(label="Blue", value="blue"),
                    discord.SelectOption(label="Green", value="green"),
                ],
            ),
            description="You can select multiple options.",
        )

        super().__init__(name_input, color_select, *args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        # Access values via children[index].item.value or .values
        name = self.children[0].item.value          # InputText -> .value
        colors = self.children[1].item.values       # Select -> .values (list)
        await interaction.response.send_message(f"Name: {name}, Colors: {colors}")
```

### Reference Implementation

See `src/cogs/join_coalition.py` for a complete example using DesignerModal with multiple select menus and text inputs.

### Documentation

- [Pycord modal_dialogs.py example](https://github.com/Pycord-Development/pycord/blob/master/examples/modal_dialogs.py)
- [Discord Components V2 API](https://discord.com/developers/docs/components/reference)

## Environment Variables

Required:
- `DISCORD_TOKEN` - Bot token from Discord Developer Portal
- `DBOT_API_URL` - Django API endpoint (default: `http://localhost:8000/api/dbot`)
- `DBOT_AUTH_KEY` - API authentication key
- `DISCORD_GUILD_ID` - Target guild ID for commands

Optional:
- `DEBUG` - Enable debug mode for `/diag` command
- `LOGFIRE_TOKEN` - Logfire write token for production (get from logfire.pydantic.dev)
- `LOGFIRE_ENVIRONMENT` - Logfire environment name (default: `development`)
- `NEW_ARRIVALS_CHANNEL_ID` - Channel ID where welcome messages are sent to new members
- `MEMBER_SYNC_INTERVAL_HOURS` - Hours between full member pushes (default: `6`)

## Code Style

- Python 3.14+
- Ruff for linting/formatting with line length 120
- Docstrings required (Google style)
- All slash commands should use `ephemeral=True` for user-facing responses
- Use `httpx.AsyncClient` for API calls with appropriate timeouts
- Log errors with `logfire`
