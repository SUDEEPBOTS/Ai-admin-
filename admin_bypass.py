# admin_bypass.py
"""
Admin check helpers for Telegram groups.
Compatible with async python-telegram-bot webhook setup.
"""

from typing import Optional
from telegram import Bot

# Optional caching to reduce repeated API calls (can be enabled)
# This avoids frequent get_chat_member calls in big GCs.
ADMIN_CACHE = {}
CACHE_TTL = 120  # 2 minutes


async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Returns True if the user is admin/creator in the given group.
    Includes safe exception handling for restricted chats.

    bot: telegram.Bot instance
    """
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        # For rare cases: chat migrated, bot lacks permission, or user not found.
        # Treat as NOT admin to avoid silent bypass.
        print(f"[is_admin] Error fetching admin info: {e}")
        return False


# ---------- OPTIONAL: cached version ---------- #
# You can use this instead if your moderation checks require many rapid calls.
# Replace your imports: from admin_bypass import is_admin_cached

async def is_admin_cached(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Cached admin check for performance in large groups.

    Cache: {(chat_id): {"admins": set(user_ids), "expires": timestamp}}
    Updates admin list only after TTL expiry.
    """
    import time

    now = time.time()
    cache = ADMIN_CACHE.get(chat_id, {})

    # If cache valid → use it
    if cache and cache.get("expires", 0) > now:
        return user_id in cache.get("admins", set())

    # Refresh admin list
    try:
        admins = await bot.get_chat_administrators(chat_id)
        admin_ids = {a.user.id for a in admins}

        ADMIN_CACHE[chat_id] = {
            "admins": admin_ids,
            "expires": now + CACHE_TTL
        }

        return user_id in admin_ids

    except Exception as e:
        print(f"[is_admin_cached] Error fetching admin list: {e}")
        # if error, fallback to per-user method
        return await is_admin(bot, chat_id, user_id)
