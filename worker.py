"""Proceso separado que consume la cola `predictions` (ver
services/queue.py). En Render se despliega como un Background Worker
aparte del servicio web — mismo repo, mismo Dockerfile, distinto start
command: `python worker.py` en vez de `uvicorn main:app`.

Correr más de una instancia de este worker es la forma de escalar
horizontalmente el cómputo pesado (Prophet/LSTM): cada instancia toma
jobs de la misma cola en Redis, no hay estado compartido en memoria
entre ellas.
"""

import os

from dotenv import load_dotenv
from redis import Redis
from rq import Worker

from services.queue import QUEUE_NAME

load_dotenv()


def main() -> None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise RuntimeError(
            "REDIS_URL no configurada — el worker no tiene de dónde tomar jobs."
        )

    connection = Redis.from_url(redis_url)
    worker = Worker([QUEUE_NAME], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
