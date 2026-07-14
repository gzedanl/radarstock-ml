import os
from typing import Optional

from redis import Redis
from rq import Queue

QUEUE_NAME = "predictions"

_queue: Optional[Queue] = None
_checked = False


def get_queue() -> Optional[Queue]:
    """None si REDIS_URL no está configurada — el caller debe caer a
    procesamiento síncrono (el comportamiento que tenía /predict antes
    de la cola). Memoiza la conexión: no reconecta en cada request."""
    global _queue, _checked

    if _checked:
        return _queue

    _checked = True
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None

    connection = Redis.from_url(redis_url)
    _queue = Queue(QUEUE_NAME, connection=connection)
    return _queue
