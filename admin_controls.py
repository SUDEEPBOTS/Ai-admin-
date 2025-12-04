# admin_controls.py
import asyncio
from telegram import ChatPermissions
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from models import (
    add_bot_admin_db,
    remove_bot_admin_db,
    is_bot_admin_db,
    list_bot_admins_db,
)

# -------- Helper: Check permissions --------
async def _can_use_admin_features(update, context):
    user = update.effective_user
    chat = update.effective_chat

    # Owner always allowed
    from config import OWNER_ID
    if OWNER_ID and user.id == OWNER_ID:
        return True

    # Bot-admins (stored in DB)
    if is_bot_admin_db(user.id):
        return True

    # Normal chat admins allowed
    try:
        member = await chat.get_member(user.id)
        if member.status in ["administrator", "creator"]:
            return True
    except:
        pass

    return False


# -------- /add_bot_admin --------
async def add_bot_admin_cmd(update, context):
    if not await _can_use_admin_features(update, context):
        return await update.message.reply_text(
            "❌ <b>You cannot use this command.</b>",
            parse_mode=ParseMode.HTML,
        )

    if not update.message.reply_to_message:
        return await update.message.reply_text(
            "Usage: Reply to a user's message → /add_bot_admin",
            parse_mode=ParseMode.HTML,
        )

    target = update.message.reply_to_message.from_user
    add_bot_admin_db(target.id)

    await update.message.reply_text(
        f"✅ <b>{target.first_name} is now a BOT-ADMIN.</b>",
        parse_mode=ParseMode.HTML,
    )


# -------- /remove_bot_admin --------
async def remove_bot_admin_cmd(update, context):
    if not await _can_use_admin_features(update, context):
        return await update.message.reply_text("❌ Not allowed.", parse_mode=ParseMode.HTML)

    if not update.message.reply_to_message:
        return await update.message.reply_text(
            "Usage: Reply to user → /remove_bot_admin",
            parse_mode=ParseMode.HTML,
        )

    target = update.message.reply_to_message.from_user
    remove_bot_admin_db(target.id)

    await update.message.reply_text(
        f"🗑️ <b>{target.first_name} removed from bot-admin list.</b>",
        parse_mode=ParseMode.HTML,
    )


# -------- /bot_admins --------
async def list_bot_admins_cmd(update, context):
    ids = list_bot_admins_db()
    if not ids:
        return await update.message.reply_text(
            "<i>No bot-admins added.</i>", parse_mode=ParseMode.HTML
        )

    text = "<b>BOT ADMINS:</b>\n\n"
    for uid in ids:
        text += f"• <code>{uid}</code>\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# -------- /make_admin (manual admin promoting) --------
async def make_admin_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    if not await _can_use_admin_features(update, context):
        return await update.message.reply_text("❌ Not allowed.", parse_mode=ParseMode.HTML)

    if not update.message.reply_to_message:
        return await update.message.reply_text(
            "Reply to a user's message and use /make_admin",
            parse_mode=ParseMode.HTML,
        )

    user = update.message.reply_to_message.from_user
    bot = context.bot
    chat = update.effective_chat

    try:
        await bot.promote_chat_member(
            chat.id,
            user.id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_restrict_members=True,
            can_promote_members=False,
            can_invite_users=True,
            can_pin_messages=True,
            can_manage_video_chats=True,
        )
        await update.message.reply_text(
            f"🎉 <b>{user.first_name} is now an ADMIN.</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed: <code>{e}</code>",
            parse_mode=ParseMode.HTML,
        )


# -------- /bot_ban (admin instructs bot to ban someone) --------
async def bot_ban_cmd(update, context):
    if not await _can_use_admin_features(update, context):
        return await update.message.reply_text("❌ Permission denied.", parse_mode=ParseMode.HTML)

    if not update.message.reply_to_message:
        return await update.message.reply_text(
            "Reply to user → /bot_ban", parse_mode=ParseMode.HTML
        )

    target = update.message.reply_to_message.from_user
    chat = update.effective_chat

    try:
        await chat.ban_member(target.id)
        await update.message.reply_text(
            f"⛔ <b>Banned {target.first_name}</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to ban: <code>{e}</code>", parse_mode=ParseMode.HTML
        )
