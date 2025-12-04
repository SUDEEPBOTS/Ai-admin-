# appeal_system.py
"""
Appeal handling for webhook + async setup (python-telegram-bot).
- Enqueues appeal evaluation to worker (RQ).
- Persists appeal counts to MongoDB so counts survive restarts.
- Notifies admin with an inline approve button when threshold is reached.
"""

import os
from typing import Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes

# DB and models
from db import get_db
import models

# enqueue helper
try:
    from enqueue_helpers import enqueue_task
except Exception:
    enqueue_task = None

# config
from config import MAX_WARNINGS

# Threshold of appeals before notifying admin (you can tune)
APPEAL_NOTIFY_THRESHOLD = int(os.getenv("APPEAL_NOTIFY_THRESHOLD", "4"))

# Collection name for persisted counts (simple key-value collection)
_db = get_db()
_counts_coll = _db.get_collection("appeal_counts")


async def _increment_appeal_count(user_id: int) -> int:
    """
    Atomically increment and return the number of appeals submitted by user_id.
    Stores a document {user_id, count, updated_at, created_at}
    """
    from datetime import datetime
    res = _counts_coll.find_one_and_update(
        {"user_id": user_id},
        {
            "$inc": {"count": 1},
            "$setOnInsert": {"created_at": datetime.utcnow()},
            "$set": {"updated_at": datetime.utcnow()}
        },
        upsert=True,
        return_document=True  # Use pymongo.ReturnDocument.AFTER if needed
    )
    if not res:
        doc = _counts_coll.find_one({"user_id": user_id})
        return doc.get("count", 1) if doc else 1
    return int(res.get("count", 1))


async def _reset_appeal_count(user_id: int) -> None:
    _counts_coll.delete_one({"user_id": user_id})


async def handle_appeal(bot, user_id: int, chat_id: int, reason: str, admin_id: int) -> bool:
    """
    Called when a user submits an appeal.
    - Enqueues evaluation via RQ worker.
    - Logs appeal in DB via models.log_appeal.
    - Increments persisted counter; if threshold reached, notifies admin with approve button.

    Returns:
      True  -> appeal forwarded to admin for manual review/approval
      False -> normal appeal flow (not forwarded)
    """
    # Log appeal in moderation DB (for history)
    try:
        models.log_appeal(user_id=user_id, chat_id=chat_id, appeal_text=reason, approved=False)
    except Exception as e:
        print("Failed to log appeal:", e)

    # Enqueue automatic evaluation of appeal (best-effort; worker will run moderation.evaluate_appeal_sync)
    try:
        if enqueue_task:
            enqueue_task("moderation.evaluate_appeal_sync", reason)
        else:
            # no enqueue available: fallback is to skip auto-eval (or run in executor)
            print("enqueue_task not available; skipping background appeal evaluation.")
    except Exception as e:
        print("Failed to enqueue appeal evaluation:", e)

    # Increment persisted appeal count
    try:
        count = await _increment_appeal_count(user_id)
    except Exception as e:
        print("Failed to increment appeal count:", e)
        # fallback to in-memory short-lived count if DB fails
        # (Not implemented here — assume DB works.)
        count = 1

    # If count reaches threshold, notify admin for manual review
    if count >= APPEAL_NOTIFY_THRESHOLD:
        try:
            btn = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Approve User", callback_data=f"appeal_approve:{user_id}:{chat_id}")]]
            )
            text = (
                f"⚠️ Appeal limit reached ({count})\n\n"
                f"User: {user_id}\n"
                f"Chat: {chat_id}\n"
                f"Reason: {reason}\n\n"
                "Click to approve the user."
            )
            await bot.send_message(admin_id, text, reply_markup=btn)
            return True
        except Exception as e:
            print("Failed to notify admin about appeal:", e)
            # still consider it handled
            return False

    return False


# ---------------- Callback handler for admin approval ----------------
async def handle_appeal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    CallbackQuery handler for inline approve button sent to admin.
    Expected callback_data format: "appeal_approve:<user_id>:<chat_id>"
    """
    try:
        query = update.callback_query
        if not query:
            return
        await query.answer()  # acknowledge callback

        data = query.data or ""
        if not data.startswith("appeal_approve:"):
            # not our callback
            return

        parts = data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("Invalid callback payload.")
            return

        try:
            user_id = int(parts[1])
            chat_id = int(parts[2])
        except Exception:
            await query.edit_message_text("Invalid user/chat id in callback.")
            return

        # Mark appeal as approved in DB (log)
        try:
            models.log_appeal(user_id=user_id, chat_id=chat_id, appeal_text="Approved by admin", approved=True)
        except Exception as e:
            print("Failed to log approval:", e)

        # Reset the appeal count for user
        try:
            await _reset_appeal_count(user_id)
        except Exception as e:
            print("Failed to reset appeal count:", e)

        # Notify admin in callback message and optionally take action (unban/unmute)
        try:
            await query.edit_message_text(f"User {user_id} approved by admin {query.from_user.id}.")
        except Exception:
            pass

        # Optionally: take Telegram API actions to unban/unmute the user.
        # This code does not automatically unban; if you want, enqueue an action
        # or perform it here using context.bot.ban_chat_member / unban etc.
        # Example (careful with permissions):
        # await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)

    except Exception as e:
        print("Error in handle_appeal_callback:", e)
