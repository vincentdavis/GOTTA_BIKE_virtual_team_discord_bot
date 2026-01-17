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

**Bot Instance:** `src/bot.py` - Creates the Discord bot with `message_content` intent enabled.

**Cog System:** All Discord commands are organized as cogs in `src/cogs/`:
- `about.py` - `/help` command
- `diagnostics.py` - `/diag` debug command (DEBUG mode only)
- `in_channel.py` - `/in_channel` filtered roster command (creates link showing only channel members)
- `join_coalition.py` - `/join_the_coalition` membership application with multi-select form
- `role_sync.py` - Syncs Discord roles to Django API (`/sync_roles`, `/sync_my_roles`)
- `team_links.py` - Magic link generation (`/team_links`)
- `welcome.py` - Sends welcome message to new members in the welcome channel
- `zwiftpower.py` - ZwiftPower/ZwiftRacing profile commands (`/my_profile`, `/teammate_profile`, `/update_zp_team`, `/update_zp_results`)

### Join Coalition Form Options

The `/join_the_coalition` command collects:
- **Reasons for joining:** Virtual Racing, Fitness and Training, Community
- **Platforms:** Zwift, Rouvy, MyWhoosh, TrainingPeaks Virtual, Other
- **Race series interest:** ZRL, TTT, ClubLadder, FRR, Women's Racing, Other

**API Communication:** Cogs authenticate to the Django backend using headers:
- `X-API-Key`: From `DBOT_AUTH_KEY` env var
- `X-Guild-Id`: From `DISCORD_GUILD_ID` env var
- `X-Discord-User-Id`: Requesting user's Discord ID

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
- `WELCOME_TEAM_CHANNEL` - Channel ID where welcome messages are sent to new members

## Code Style

- Python 3.14+
- Ruff for linting/formatting with line length 120
- Docstrings required (Google style)
- All slash commands should use `ephemeral=True` for user-facing responses
- Use `httpx.AsyncClient` for API calls with appropriate timeouts
- Log errors with `logfire`
