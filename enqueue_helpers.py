# enqueue_helpers.py
import os
import importlib
from rq import Queue
from redis import Redis
from config import REDIS_URL

# Redis connection
redis_conn = Redis.from_url(REDIS_URL)

# Main queue
queue = Queue("default", connection=redis_conn)


def enqueue_task(func_path: str, *args, **kwargs):
    """
    func_path example:
      "moderation.process_message_sync"
      "moderation.evaluate_appeal_sync"
    
    Automatically imports and enqueues.
    """
    module_name, func_name = func_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)
    job = queue.enqueue(func, *args, **kwargs)
    return job
