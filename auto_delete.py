# auto_delete.py
"""
Auto-delete helper for messages.

Includes:
1) Simple async-based delayed delete (compatible with webhook).
2) Highly optimized JobQueue-based delete (recommended for large groups).
"""

import asyncio
from telegram import Bot
from telegram.ext import ContextTypes


# ----------------------------------------------------------
# Version 1: Simple async delete (your original method improved)
# ----------------------------------------------------------

async def auto_delete(bot: Bot, chat_id: int, text: str, delay: int = 9):
    """
    Sends a message and deletes it after `delay` seconds.
    Simple approach using asyncio.sleep().
    """
    try:
        msg = await bot.send_message(chat_id, text)
    except Exception as e:
        print("[auto_delete] failed to send message:", e)
        return

    try:
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass  # ignore deletion errors


# ----------------------------------------------------------
# Version 2: JobQueue Optimized Auto Delete (Recommended)
# ----------------------------------------------------------

async def _delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    """
    INTERNAL job callback — deletes a message.
    """
    job_data = context.job.data or {}
    chat_id = job_data.get("chat_id")
    message_id = job_data.get("message_id")

    if not chat_id or not message_id:
        return

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def auto_delete_job(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, delay: int = 9):
    """
    Sends a message and schedules deletion using JobQueue — best for large groups.
    Does NOT block the async loop.
    """
    try:
        msg = await context.bot.send_message(chat_id, text)
    except Exception as e:
        print("[auto_delete_job] send failed:", e)
        return

    # schedule deletion
    try:
        context.job_queue.run_once(
            _delete_message_job,
            delay,
            data={"chat_id": msg.chat_id, "message_id": msg.message_id}
        )
    except Exception as e:
        print("[auto_delete_job] scheduling failed:", e)


# ----------------------------------------------------------
# Exported names
# ----------------------------------------------------------

__all__ = [
    "auto_delete",
    "auto_delete_job",
]
