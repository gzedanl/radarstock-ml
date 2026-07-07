import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_store: dict[str, tuple[float, Any]] = {}


def cached(key: str, ttl_seconds: int, fetch_fn: Callable[[], Any]) -> Optional[Any]:
    """Cache genérico en memoria con TTL, usado por todas las fuentes
    externas (Fase 3.4). Si fetch_fn falla, loguea el error y devuelve el
    valor cacheado aunque esté vencido (o None si nunca se obtuvo) — así
    ninguna fuente externa caída rompe /predict."""
    now = time.time()

    if key in _store:
        expires_at, value = _store[key]
        if now < expires_at:
            return value

    try:
        value = fetch_fn()
    except Exception:
        logger.exception("Error refrescando cache para %s", key)
        if key in _store:
            return _store[key][1]
        return None

    _store[key] = (now + ttl_seconds, value)
    return value
