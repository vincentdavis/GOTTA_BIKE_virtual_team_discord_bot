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
- `role_sync.py` - Syncs Discord roles to Django API (`/sync_roles`, `/sync_my_roles`)
- `team_links.py` - Magic link generation (`/team_links`)
- `zwiftpower.py` - ZwiftPower/ZwiftRacing profile commands (`/my_profile`, `/teammate_profile`, `/update_zp_team`, `/update_zp_results`)

**API Communication:** Cogs authenticate to the Django backend using headers:
- `X-API-Key`: From `DBOT_AUTH_KEY` env var
- `X-Guild-Id`: From `DISCORD_GUILD_ID` env var
- `X-Discord-User-Id`: Requesting user's Discord ID

## Environment Variables

Required:
- `DISCORD_TOKEN` - Bot token from Discord Developer Portal
- `DBOT_API_URL` - Django API endpoint (default: `http://localhost:8000/api/dbot`)
- `DBOT_AUTH_KEY` - API authentication key
- `DISCORD_GUILD_ID` - Target guild ID for commands

Optional:
- `DEBUG` - Enable debug mode for `/diag` command
- `LOGFIRE_ENVIRONMENT` - Logfire environment name (default: `development`)

## Code Style

- Python 3.14+
- Ruff for linting/formatting with line length 120
- Docstrings required (Google style)
- All slash commands should use `ephemeral=True` for user-facing responses
- Use `httpx.AsyncClient` for API calls with appropriate timeouts
- Log errors with `logfire`
