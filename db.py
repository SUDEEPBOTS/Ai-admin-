# db.py
import os
import sys
from typing import Optional
from dotenv import load_dotenv

# prefer config.py but fallback to env
try:
    from config import MONGO_URI as CONFIG_MONGO_URI, DB_NAME as CONFIG_DB_NAME
except Exception:
    CONFIG_MONGO_URI = None
    CONFIG_DB_NAME = None

load_dotenv()

MONGO_URI = CONFIG_MONGO_URI or os.environ.get("MONGO_URI")
DB_NAME = CONFIG_DB_NAME or os.environ.get("DB_NAME") or os.environ.get("DATABASE_NAME")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set. Set it in config.py or environment variable MONGO_URI.")

if not DB_NAME:
    raise RuntimeError("DB_NAME is not set. Set it in config.py or environment variable DB_NAME / DATABASE_NAME.")

# Use pymongo with sensible defaults for connection pooling and timeouts.
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, PyMongoError

# Recommended options:
# - serverSelectionTimeoutMS: fail fast if DB is unreachable
# - socketTimeoutMS / connectTimeoutMS: sensible timeouts
# - maxPoolSize: control concurrency (adjust based on your plan)
# - minPoolSize: keep some connections warm
# - tz_aware: store datetimes with timezone-awareness
# - retryWrites: True for safer writes (depends on cluster)
client_options = {
    "serverSelectionTimeoutMS": int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", 5000)),
    "connectTimeoutMS": int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", 10000)),
    "socketTimeoutMS": int(os.environ.get("MONGO_SOCKET_TIMEOUT_MS", 0)),  # 0 means no timeout on sockets
    "maxPoolSize": int(os.environ.get("MONGO_MAX_POOL_SIZE", 100)),
    "minPoolSize": int(os.environ.get("MONGO_MIN_POOL_SIZE", 0)),
    "tls": os.environ.get("MONGO_TLS", "true").lower() in ("1", "true", "yes"),
    "tz_aware": True,
    "retryWrites": True,
}

# Create client
try:
    mongo_client = MongoClient(MONGO_URI, **client_options)
    db = mongo_client[DB_NAME]
except PyMongoError as e:
    # Provide an informative error message for startup logs
    raise RuntimeError(f"Failed to create MongoDB client: {e}") from e


def get_db():
    """Return the database instance."""
    return db


def close():
    """Close client connection (call on shutdown)."""
    try:
        mongo_client.close()
    except Exception:
        pass


def ensure_connection(timeout_ms: Optional[int] = None) -> bool:
    """
    Perform a quick server selection to ensure the DB is reachable.
    Raises RuntimeError on failure.
    """
    try:
        # server_info checks the server is reachable; uses serverSelectionTimeoutMS
        mongo_client.server_info()
        return True
    except ServerSelectionTimeoutError as e:
        raise RuntimeError(f"MongoDB server selection timed out: {e}") from e
    except Exception as e:
        raise RuntimeError(f"MongoDB connection check failed: {e}") from e
