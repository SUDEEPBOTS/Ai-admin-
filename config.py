# config.py
"""
Central configuration for the bot.
Reads values from environment variables (dotenv or host environment).
Keep secrets out of source control.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Required / important secrets
BOT_TOKEN = os.getenv("BOT_TOKEN")  # required
# Gemini / GenAI API key - support both common names
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GENIE_KEY") or os.getenv("GOOGLE_GENAI_KEY")

# MongoDB
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "telegram_ai_mod")

# Webhook host (public HTTPS URL of your app, e.g. https://your-app.up.railway.app)
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # required for webhook mode

# Redis for RQ
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Owner ID (bot owner / admin) - optional
def _to_int(env_val, default=0):
    try:
        return int(env_val)
    except Exception:
        return default

OWNER_ID = _to_int(os.getenv("OWNER_ID"), 0)

# Logger chat id (for bot logs). If missing, set to 0 (disabled).
LOGGER_CHAT_ID = _to_int(os.getenv("LOGGER_CHAT_ID"), 0)

# Behavior settings (tweak as needed)
MAX_WARNINGS = int(os.getenv("MAX_WARNINGS", "3"))
MUTE_DURATION_MIN = int(os.getenv("MUTE_DURATION_MIN", "10"))

ENABLE_AUTO_DELETE = os.getenv("ENABLE_AUTO_DELETE", "true").lower() in ("1", "true", "yes")
ENABLE_AUTO_MUTE = os.getenv("ENABLE_AUTO_MUTE", "true").lower() in ("1", "true", "yes")
ENABLE_AUTO_BAN = os.getenv("ENABLE_AUTO_BAN", "true").lower() in ("1", "true", "yes")

# Misc
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # production / staging / development

# Simple validator to help during startup
def validate_config(raise_on_missing: bool = False) -> dict:
    """
    Returns a dict describing missing/available critical config.
    If raise_on_missing=True, raises RuntimeError when required keys are missing.
    Call this at app startup to fail fast when something critical is not set.
    """
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not WEBHOOK_HOST:
        missing.append("WEBHOOK_HOST")
    if not MONGO_URI:
        missing.append("MONGO_URI")
    # GEMINI key may be optional if you don't use AI features.
    info = {
        "BOT_TOKEN": bool(BOT_TOKEN),
        "WEBHOOK_HOST": bool(WEBHOOK_HOST),
        "MONGO_URI": bool(MONGO_URI),
        "GEMINI_API_KEY": bool(GEMINI_API_KEY),
        "REDIS_URL": bool(REDIS_URL),
        "missing": missing,
    }
    if raise_on_missing and missing:
        raise RuntimeError(f"Missing required config keys: {', '.join(missing)}")
    return info


# Optional: call validate_config(raise_on_missing=True) in startup to fail fast.
if __name__ == "__main__":
    # For quick local testing
    print("Config test:", validate_config())
