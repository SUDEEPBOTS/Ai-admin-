# admin_power_ai.py
import google.generativeai as genai
import os
from telegram.constants import ParseMode

from models import is_bot_admin_db

try:
    from config import GEMINI_API_KEY, OWNER_ID
except:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OWNER_ID = None

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")


async def _is_allowed(update, context):
    user = update.effective_user
    chat = update.effective_chat

    if OWNER_ID and user.id == OWNER_ID:
        return True

    if is_bot_admin_db(user.id):
        return True

    try:
        member = await chat.get_member(user.id)
        return member.status in ["administrator", "creator"]
    except:
        return False


async def nl_admin_ai_handler(update, context):
    """
    AI-based natural language admin commands.
    Example:
    "isko admin bnao", "make him admin", "promote this user"
    """

    if not update.message:
        return

    text = update.message.text.lower()
    if update.effective_chat.type == "private":
        return

    # Required: reply to user
    if not update.message.reply_to_message:
        return

    if not await _is_allowed(update, context):
        return

    # Ask AI what user wants
    prompt = f"""
    You are an AI that understands admin requests in Indian slang.

    If the message means "make this replied user an admin",
    reply with EXACT JSON only:

    {{"action": "promote"}}

    If the message does NOT mean admin promotion:

    {{"action": "ignore"}}

    Message: "{text}"
    """

    try:
        res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        action = res.text.strip()
    except:
        return  # silently ignore

    if '"promote"' not in action:
        return

    # Promote the replied user
    target = update.message.reply_to_message.from_user
    chat = update.effective_chat
    bot = context.bot

    try:
        await bot.promote_chat_member(
            chat.id,
            target.id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_invite_users=True,
            can_manage_video_chats=True,
        )

        await update.message.reply_text(
            f"🎉 <b>{target.first_name} is now an ADMIN — approved via AI!</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to promote:\n<code>{e}</code>",
            parse_mode=ParseMode.HTML,
        )
