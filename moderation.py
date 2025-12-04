# moderation.py
import json
import os
from typing import Dict, Any

# Gemini SDK (blocking) - used inside worker sync functions
import google.generativeai as genai

# Try to read key from config or env
try:
    # if you have config.py with GEMINI_API_KEY, prefer it
    from config import GEMINI_API_KEY
except Exception:
    GEMINI_API_KEY = os.environ.get("GENIE_KEY") or os.environ.get("GEMINI_API_KEY")

# RQ enqueue helper (used by async handler)
try:
    from enqueue_helpers import enqueue_task
except Exception:
    enqueue_task = None  # if not present, handler will fallback to run sync in executor

# ---------- Lazy model init ----------
_moderation_model = None
_appeal_model = None
_models_initialized = False


def _init_models():
    """Initialize Gemini SDK and model objects lazily (call inside worker)."""
    global _models_initialized, _moderation_model, _appeal_model
    if _models_initialized:
        return
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI API key not set (GEMINI_API_KEY / GENIE_KEY).")
    genai.configure(api_key=GEMINI_API_KEY)
    # choose model names as per earlier file
    _moderation_model = genai.GenerativeModel("gemini-2.5-flash")
    _appeal_model = genai.GenerativeModel("gemini-2.5-flash")
    _models_initialized = True


# ---------- Utilities ----------
def safe_json(text: str, default: Dict[str, Any]):
    try:
        j = json.loads(text)
        return j if isinstance(j, dict) else default
    except Exception:
        return default


# ---------- Moderation logic (sync functions for worker) ----------
MODERATION_SYS = """
You are an AI moderator for a Telegram group chat.

Follow:
1. Universal safety rules
2. Custom group rules provided

Actions:
- allow
- warn
- mute
- ban
- delete

Return ONLY a JSON:
{
 "action": "...",
 "reason": "...",
 "category": "...",
 "severity": 1-5,
 "should_delete": true/false
}
"""


def moderate_message_sync(text: str, user: Dict[str, Any], chat: Dict[str, Any], rules_text: str):
    """
    Blocking moderation call suitable for running inside an RQ worker.
    user and chat are dict-like objects (serializable) from update.to_dict().
    Returns a dict with keys: action, reason, category, severity, should_delete
    """
    _init_models()

    username = f"@{user.get('username')}" if user and user.get("username") else (user.get("first_name") if user else "unknown")
    chat_title = (chat.get("title") if chat else str(chat.get("id") if chat else "unknown"))

    prompt = f"""
{MODERATION_SYS}

GROUP RULES:
{rules_text or "<no custom rules provided>"}

CHAT:
{chat_title}

USER:
{username} (ID: {user.get("id") if user else 'unknown'})

MESSAGE:
{text}
"""

    default = {
        "action": "allow",
        "reason": "AI error",
        "category": "other",
        "severity": 1,
        "should_delete": False
    }

    try:
        res = _moderation_model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        data = safe_json(res.text.strip(), default)
        return data
    except Exception as e:
        # best effort return default
        return default


# Worker-facing function that processes an entire update (serializable dict)
def process_message_sync(update_dict: Dict[str, Any], rules_text: str = "") -> Dict[str, Any]:
    """
    Called by RQ worker. Expects update.to_dict() as input.
    Returns dict with processing result (useful for logging).
    """
    try:
        # Extract message text and user/chat fields carefully
        message = update_dict.get("message") or update_dict.get("edited_message") or {}
        text = message.get("text") or message.get("caption") or ""
        user = message.get("from") or {}
        chat = message.get("chat") or {}
        # Call moderation logic
        mod_result = moderate_message_sync(text, user, chat, rules_text)
        # Here: apply actions e.g., DB updates, call Telegram API to ban/mute/delete
        # NOTE: This function runs in worker context; it does NOT have bot object.
        # You should implement post-processing (sending messages/moderation actions)
        # by either using a stored bot token + REST calls or by pushing results to another queue
        # that a 'web' process will consume to execute Telegram API actions.
        return {"status": "ok", "moderation": mod_result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------- Appeal evaluation (sync) ----------
APPEAL_SYS = """
You review Telegram ban appeals.

Approve if:
- user is genuinely sorry
- promises to follow rules

Reject if:
- still abusive
- fake apology
- trolling

Return only JSON:
{
 "approve": true/false,
 "reason": "..."
}
"""


def evaluate_appeal_sync(text: str):
    """Blocking evaluation of appeals - run inside worker."""
    _init_models()

    default = {"approve": False, "reason": "AI error"}

    try:
        res = _appeal_model.generate_content(
            f"{APPEAL_SYS}\n\nUSER APPEAL:\n{text}",
            generation_config={"response_mime_type": "application/json"},
        )
        return safe_json(res.text.strip(), default)
    except Exception:
        return default


# ---------- Async handler (used by webhook process) ----------
async def handle_message(update, context):
    """
    Async handler to be registered with PTB Application in webhook mode.
    This should *not* perform heavy work; it enqueues a job and returns quickly.
    """
    # Quick acknowledgement - optional (you can remove to avoid extra messages)
    try:
        if update.message and update.message.chat:
            # optional: do a light ack only in private chats or when necessary
            # await update.message.reply_text("Queued for moderation.")
            pass
    except Exception:
        pass

    # Enqueue for background processing
    try:
        if enqueue_task:
            # enqueue process_message_sync in the worker; pass update as serializable dict
            job = enqueue_task("moderation.process_message_sync", update.to_dict())
            # optionally store job.id/log it
            # print("Enqueued moderation job:", getattr(job, "id", None))
        else:
            # fallback: if enqueue helper is not available, run processing in thread pool (not recommended)
            import asyncio
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, process_message_sync, update.to_dict(), "")
    except Exception as e:
        # enqueue failing shouldn't crash handler
        print("Failed to enqueue moderation job:", e)

    # handler returns quickly


# ---------- Appeal async wrapper (enqueues appeal eval) ----------
async def handle_appeal_submission(update, context):
    """
    Example async wrapper to enqueue an appeal evaluation (when a user submits an appeal).
    """
    text = ""
    if update.message:
        text = update.message.text or ""
    try:
        if enqueue_task:
            enqueue_task("moderation.evaluate_appeal_sync", text)
        else:
            import asyncio
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, evaluate_appeal_sync, text)
    except Exception as e:
        print("Failed to enqueue appeal evaluation:", e)


# Exported names for other modules
__all__ = [
    "handle_message",
    "handle_appeal_submission",
    "process_message_sync",
    "moderate_message_sync",
    "evaluate_appeal_sync",
]
