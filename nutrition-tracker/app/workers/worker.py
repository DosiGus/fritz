import logging

import redis
from rq import Queue, Worker

from app.config import settings
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

QUEUE_VOICE = "nutrition-voice"
QUEUE_JOBS = "nutrition-jobs"


def get_redis_connection() -> redis.Redis:
    return redis.from_url(settings.redis_url)


def get_voice_queue() -> Queue:
    return Queue(QUEUE_VOICE, connection=get_redis_connection())


def get_jobs_queue() -> Queue:
    return Queue(QUEUE_JOBS, connection=get_redis_connection())


if __name__ == "__main__":
    conn = get_redis_connection()
    queues = [Queue(QUEUE_VOICE, connection=conn), Queue(QUEUE_JOBS, connection=conn)]
    logger.info("worker_starting", extra={"queues": [q.name for q in queues]})
    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=True)
