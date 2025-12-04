# worker.py
import os
import sys
from rq import Worker, Queue, Connection
from redis import Redis
from config import REDIS_URL

listen = ["default"]

def main():
    redis_conn = Redis.from_url(REDIS_URL)
    with Connection(redis_conn):
        worker = Worker(list(map(Queue, listen)))
        worker.work()

if __name__ == "__main__":
    main()
