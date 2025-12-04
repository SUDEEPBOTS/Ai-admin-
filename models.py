# models.py
from datetime import datetime
from typing import List, Dict, Any, Optional
from pymongo import ASCENDING, IndexModel, ReturnDocument
from pymongo.collection import Collection
from db import db

# NOTE:
# - db is expected to be a module export that provides the MongoDB database object,
#   e.g., in db.py: client = MongoClient(...); db = client.get_database(...)
# - Call ensure_indexes() once at startup (web process or worker) to create indexes.


# ---------- Groups ----------
def add_group(chat_id: int, title: str, added_by: int) -> None:
    """
    Upsert a group document.
    """
    db.groups.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "title": title,
                "added_by": added_by,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {"chat_id": chat_id, "created_at": datetime.utcnow()}
        },
        upsert=True
    )


# ---------- Users ----------
def add_user(user_id: int, username: Optional[str]) -> None:
    """
    Upsert a user document.
    """
    db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "username": username,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {"user_id": user_id, "created_at": datetime.utcnow()}
        },
        upsert=True
    )


# ---------- Rules ----------
def add_rule_db(chat_id: int, rule: str) -> None:
    db.rules.insert_one({
        "chat_id": chat_id,
        "rule": rule,
        "created_at": datetime.utcnow()
    })


def get_rules_db(chat_id: int) -> List[str]:
    """
    Return list of rule strings for the chat_id.
    """
    cursor = db.rules.find({"chat_id": chat_id}, {"rule": 1, "_id": 0})
    return [r.get("rule") for r in cursor]


# ---------- Warnings ----------
def increment_warning(chat_id: int, user_id: int) -> int:
    """
    Atomically increment warning count and return the new value.
    Uses find_one_and_update with $inc and upsert to ensure atomicity.
    """
    res = db.warnings.find_one_and_update(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$inc": {"warnings": 1},
            "$setOnInsert": {"created_at": datetime.utcnow()}
        },
        upsert=True,
        return_document=True  # return the updated document (requires pymongo ReturnDocument)
    )
    # res can be None in some very rare cases; handle defensively
    if not res:
        # read back
        doc = db.warnings.find_one({"chat_id": chat_id, "user_id": user_id})
        return doc.get("warnings", 1) if doc else 1
    return int(res.get("warnings", 1))


def reset_warnings(chat_id: int, user_id: int) -> None:
    db.warnings.delete_one({"chat_id": chat_id, "user_id": user_id})


def get_all_warnings(chat_id: int) -> List[Dict[str, Any]]:
    """
    Returns a list of warning documents for a chat.
    """
    return list(db.warnings.find({"chat_id": chat_id}))


# ---------- Appeals ----------
def log_appeal(user_id: int, chat_id: int, appeal_text: str, approved: bool) -> None:
    db.appeals.insert_one({
        "user_id": user_id,
        "chat_id": chat_id,
        "appeal_text": appeal_text,
        "approved": bool(approved),
        "created_at": datetime.utcnow()
    })


# ---------- Moderation Logs ----------
def log_action(chat_id: int, user_id: int, action: str, reason: str) -> None:
    db.moderation_logs.insert_one({
        "chat_id": chat_id,
        "user_id": user_id,
        "action": action,
        "reason": reason,
        "created_at": datetime.utcnow()
    })


# ---------- Approvals (new) ----------
def approve_user_db(chat_id: int, user_id: int, approver_id: int) -> None:
    """
    Mark a user as approved in a chat (upsert).
    """
    db.approved_users.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$set": {
                "chat_id": chat_id,
                "user_id": user_id,
                "approved_by": approver_id,
                "approved_at": datetime.utcnow()
            }
        },
        upsert=True
    )


def unapprove_user_db(chat_id: int, user_id: int) -> None:
    """
    Remove a single user's approval in a chat.
    """
    db.approved_users.delete_one({"chat_id": chat_id, "user_id": user_id})


def is_user_approved_db(chat_id: int, user_id: int) -> bool:
    """
    Returns True if the user is approved in the given chat.
    """
    doc = db.approved_users.find_one({"chat_id": chat_id, "user_id": user_id}, {"_id": 0})
    return bool(doc)


def unapprove_all_db(chat_id: int) -> int:
    """
    Remove all approvals for a chat. Returns the number removed.
    """
    res = db.approved_users.delete_many({"chat_id": chat_id})
    return res.deleted_count if res else 0


def count_approved_db(chat_id: int) -> int:
    """
    Return the total number of approved users in a chat.
    """
    return db.approved_users.count_documents({"chat_id": chat_id})


def get_approved_users_db(chat_id: int) -> List[int]:
    """
    Return list of user_ids approved in the chat.
    """
    docs = db.approved_users.find({"chat_id": chat_id}, {"user_id": 1, "_id": 0})
    return [d["user_id"] for d in docs]


# ---------- Indexes (call at startup) ----------
def ensure_indexes() -> None:
    """
    Create recommended indexes for fast queries.
    Call this once at application startup (both web and worker processes can call).
    """
    # groups: unique on chat_id
    try:
        db.groups.create_indexes([
            IndexModel([("chat_id", ASCENDING)], name="idx_groups_chat_id", unique=True)
        ])
    except Exception:
        pass

    # users: unique on user_id
    try:
        db.users.create_indexes([
            IndexModel([("user_id", ASCENDING)], name="idx_users_user_id", unique=True)
        ])
    except Exception:
        pass

    # rules: index on chat_id
    try:
        db.rules.create_indexes([
            IndexModel([("chat_id", ASCENDING)], name="idx_rules_chat_id")
        ])
    except Exception:
        pass

    # warnings: composite index for chat+user lookups
    try:
        db.warnings.create_indexes([
            IndexModel([("chat_id", ASCENDING), ("user_id", ASCENDING)], name="idx_warnings_chat_user", unique=True)
        ])
    except Exception:
        pass

    # appeals: index on user_id and chat_id for history lookups
    try:
        db.appeals.create_indexes([
            IndexModel([("user_id", ASCENDING)], name="idx_appeals_user"),
            IndexModel([("chat_id", ASCENDING)], name="idx_appeals_chat")
        ])
    except Exception:
        pass

    # moderation_logs: index commonly queried fields
    try:
        db.moderation_logs.create_indexes([
            IndexModel([("chat_id", ASCENDING)], name="idx_modlogs_chat"),
            IndexModel([("user_id", ASCENDING)], name="idx_modlogs_user")
        ])
    except Exception:
        pass

    # approved_users: ensure fast lookup per chat+user, unique constraint
    try:
        db.approved_users.create_indexes([
            IndexModel([("chat_id", ASCENDING), ("user_id", ASCENDING)], name="idx_approved_chat_user", unique=True),
            IndexModel([("chat_id", ASCENDING)], name="idx_approved_chat")
        ])
    except Exception:
        pass
