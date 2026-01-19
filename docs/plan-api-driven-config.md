# Plan: API-Driven Bot Configuration

## Overview

Move bot configuration (messages, form options, channel settings) from hardcoded values to the Django API, with periodic refresh every 5-10 minutes.

## Implementation

### 1. Create Config Service (`src/services/config.py`)

A centralized service that:
- Fetches configuration from API on bot startup
- Caches in memory
- Refreshes every 5 minutes using `discord.ext.tasks`
- Falls back to defaults if API unavailable

```python
# Structure
class BotConfig:
    channels: ChannelConfig      # welcome_channel, notification_channel, etc.
    messages: MessageConfig      # welcome_text, button_labels, response_templates
    forms: FormConfig           # join_reasons, platforms, race_series options
    _last_refresh: datetime

    async def refresh() -> None
    def get_channel(name: str) -> int | None
    def get_message(key: str) -> str
    def get_form_options(form: str, field: str) -> list[str]
```

### 2. API Endpoint (Django side)

`GET /api/dbot/config`

```json
{
  "channels": {
    "welcome_team": "123456789",
    "notifications": "987654321"
  },
  "messages": {
    "welcome_greeting": "Hello {mention} Welcome to THE COALITION...",
    "welcome_join_prompt": "Please complete our membership application...",
    "join_button_label": "Join The Coalition",
    "application_submitted": "{name} please complete your application here. {url}"
  },
  "forms": {
    "join_coalition": {
      "reasons": ["Virtual Racing", "Fitness and Training", "Community"],
      "platforms": ["Zwift", "Rouvy", "MyWhoosh", "TrainingPeaks Virtual", "Other"],
      "race_series": ["ZRL", "TTT", "ClubLadder", "FRR", "Women's Racing", "Other"]
    }
  }
}
```

### 3. Update Cogs

**Files to modify:**
- `src/cogs/welcome.py` - Use config for messages and channel
- `src/cogs/join_coalition.py` - Use config for form options and messages
- `src/cogs/about.py` - Use config for help text
- `src/bot.py` - Initialize config service

**Pattern change:**
```python
# Before (hardcoded)
welcome_message = f"Hello {member.mention} Welcome to THE COALITION..."

# After (from config)
from src.services.config import bot_config
welcome_message = bot_config.get_message("welcome_greeting").format(mention=member.mention)
```

### 4. Default Fallbacks

Keep current hardcoded values as defaults in `src/services/defaults.py` so bot works even if API is unavailable.

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/services/__init__.py` | Create | Package init |
| `src/services/config.py` | Create | Config service with caching |
| `src/services/defaults.py` | Create | Default values fallback |
| `src/cogs/welcome.py` | Modify | Use config service |
| `src/cogs/join_coalition.py` | Modify | Use config service |
| `src/bot.py` | Modify | Initialize config on startup |

## Verification

1. Start bot without API running → should use defaults
2. Start bot with API → should fetch config
3. Change config in Django admin → wait 5 min → bot uses new values
4. Test `/test_welcome` → shows configured message
5. Test `/join_the_coalition` → shows configured form options
