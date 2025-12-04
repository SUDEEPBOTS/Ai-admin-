# approvals.py
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from models import (
    approve_user_db,
    unapprove_user_db,
    unapprove_all_db,
    is_user_approved_db,
    count_approved_db,
)


# -------------- /approve (reply-based approval) ----------------

async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    bot = context.bot

    # Only admins may use /approve
    member = await chat.get_member(update.effective_user.id)
    if member.status not in ("administrator", "creator"):
        return await message.reply_text(
            "<b>❌ Only admins can approve users.</b>",
            parse_mode=ParseMode.HTML
        )

    # Must be reply
    if not message.reply_to_message:
        return await message.reply_text(
            "<b>Usage:</b> Reply to a user's message with /approve",
            parse_mode=ParseMode.HTML
        )

    target = message.reply_to_message.from_user
    chat_id = chat.id
    target_id = target.id

    # Mark approved
    approve_user_db(chat_id, target_id, update.effective_user.id)

    # Count total approved
    total = count_approved_db(chat_id)

    uname = f"@{target.username}" if target.username else "—"

    text = f"""
<b>✅ USER APPROVED SUCCESSFULLY</b>

<b>Name:</b> {target.first_name}
<b>Username:</b> {uname}
<b>User ID:</b> <code>{target_id}</code>

<b>Total Approved Users:</b> <code>{total}</code>
"""

    await message.reply_text(text, parse_mode=ParseMode.HTML)


# -------------- /unapprove (single user) ----------------

async def unapprove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat

    # Admin check
    member = await chat.get_member(update.effective_user.id)
    if member.status not in ("administrator", "creator"):
        return await message.reply_text(
            "<b>❌ Only admins can unapprove.</b>",
            parse_mode=ParseMode.HTML
        )

    # Must be reply
    if not message.reply_to_message:
        return await message.reply_text(
            "<b>Usage:</b> Reply to user → /unapprove</b>",
            parse_mode=ParseMode.HTML
        )

    target = message.reply_to_message.from_user
    chat_id = chat.id
    target_id = target.id

    unapprove_user_db(chat_id, target_id)

    await message.reply_text(
        f"<b>🚫 User Unapproved:</b> {target.first_name}",
        parse_mode=ParseMode.HTML
    )


# -------------- /unapprove_all ----------------

async def unapprove_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat

    # Admin check
    member = await chat.get_member(update.effective_user.id)
    if member.status not in ("administrator", "creator"):
        return await message.reply_text(
            "<b>❌ Only admins can reset approvals.</b>",
            parse_mode=ParseMode.HTML
        )

    removed = unapprove_all_db(chat.id)

    await message.reply_text(
        f"<b>🧹 All approvals cleared!</b>\nRemoved: <code>{removed}</code>",
        parse_mode=ParseMode.HTML
    )


# -------------- Helper: should the message be moderated? ----------------

def should_moderate(chat_id: int, user_id: int) -> bool:
    """
    Returns False if user is approved → bot will ignore moderation
    """
    return not is_user_approved_db(chat_id, user_id)
