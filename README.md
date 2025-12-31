# GOTTA.BIKE Virtual Team Discord Bot

A Discord bot for managing Zwift racing teams. Built with [py-cord](https://docs.pycord.dev/) and designed to integrate with a Django backend API for team management features.

## Features

### Slash Commands

| Command | Description | Permissions |
|---------|-------------|-------------|
| `/help` | Get philosophical wisdom about Zwift racing | Everyone |
| `/team_links` | Generate a magic link to access the team links page | Everyone |
| `/my_profile` | View your ZwiftPower and Zwift Racing profile | Everyone |
| `/teammate_profile` | Search and view a teammate's profile | Everyone |
| `/sync_my_roles` | Sync your Discord roles to the team database | Everyone |
| `/sync_roles` | Manually sync all guild roles to the database | Admin |
| `/update_zp_team` | Trigger ZwiftPower team roster update | Admin |
| `/update_zp_results` | Trigger ZwiftPower results update | Admin |
| `/diag` | Debug diagnostics (DEBUG mode only) | Everyone |

### Automatic Role Syncing

The bot automatically syncs Discord roles to the Django backend:
- Syncs all guild roles on startup
- Listens for role create/update/delete events
- Syncs user roles when they change
- Runs periodic sync every hour

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager
- Discord bot token
- Django backend API (for team management features)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd GOTTA_BIKE_virtual_team_discord_bot
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Create a `.env` file with the required environment variables:
   ```env
   DISCORD_TOKEN=your_discord_bot_token
   DBOT_API_URL=http://localhost:8000/api/dbot
   DBOT_AUTH_KEY=your_api_key
   DISCORD_GUILD_ID=your_guild_id
   ```

## Usage

### Running Locally

```bash
uv run main.py
```

### Running with Docker

```bash
docker build -t coalition-bot .
docker run --env-file .env coalition-bot
```

## Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `DISCORD_TOKEN` | Yes | Bot token from Discord Developer Portal | - |
| `DBOT_API_URL` | Yes | Django API endpoint | `http://localhost:8000/api/dbot` |
| `DBOT_AUTH_KEY` | Yes | API authentication key | - |
| `DISCORD_GUILD_ID` | Yes | Target guild ID for commands | - |
| `DEBUG` | No | Enable debug mode for `/diag` command | `false` |
| `LOGFIRE_ENVIRONMENT` | No | Logfire environment name | `development` |

## Project Structure

```
.
├── main.py              # Entry point - configures logging, loads cogs, starts bot
├── src/
│   ├── bot.py           # Bot instance configuration
│   └── cogs/
│       ├── about.py         # /help command
│       ├── diagnostics.py   # /diag debug command
│       ├── role_sync.py     # Role syncing commands and listeners
│       ├── team_links.py    # Magic link generation
│       └── zwiftpower.py    # ZwiftPower/ZwiftRacing profile commands
├── Dockerfile
├── pyproject.toml
└── ruff.toml
```

## API Authentication

The bot authenticates to the Django backend using HTTP headers:

| Header | Description |
|--------|-------------|
| `X-API-Key` | API authentication key from `DBOT_AUTH_KEY` |
| `X-Guild-Id` | Guild ID from `DISCORD_GUILD_ID` |
| `X-Discord-User-Id` | Requesting user's Discord ID |

## Development

### Linting and Formatting

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### Type Checking

```bash
uv run ty check
```

### Code Style

- Line length: 120 characters
- Google-style docstrings
- All slash commands use `ephemeral=True` for user-facing responses
- Use `httpx.AsyncClient` for API calls with appropriate timeouts
- Log errors with `logfire`

## Dependencies

- **py-cord** - Discord API wrapper (fork of discord.py)
- **httpx** - Async HTTP client for API communication
- **logfire** - Observability and logging
- **python-dotenv** - Environment variable management
- **beautifulsoup4** - HTML parsing utilities

## License

MIT License - see [LICENSE.md](LICENSE.md)