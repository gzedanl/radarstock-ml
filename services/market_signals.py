import logging
from typing import Optional

import httpx

from models.schemas import AlertaInsumo
from services.cache import cached

logger = logging.getLogger(__name__)

TTL_COMMODITIES = 12 * 3600
UMBRAL_ALERTA_PCT = 8.0

# Nota sobre el índice de flete marítimo (Freightos Baltic Index):
# no encontramos una fuente pública gratuita con acceso programático
# simple (sin registro/pago) para este dato. Se omite por ahora — no
# inventamos un endpoint. Se puede agregar cuando se consiga acceso real.

# Rubro -> [(símbolo de Yahoo Finance, nombre legible)]. Empezamos con
# 5 rubros comunes; fácil de extender agregando otra entrada acá.
RUBRO_COMMODITIES: dict[str, list[tuple[str, str]]] = {
    "textil": [("CT=F", "algodón")],
    "alimentos": [("ZW=F", "trigo"), ("ZL=F", "aceite de soja")],
    "ferreteria": [("HG=F", "cobre"), ("CL=F", "petróleo (insumo de plásticos)")],
    "plasticos": [("CL=F", "petróleo (insumo de plásticos)")],
    "transporte": [("CL=F", "petróleo")],
}


def _normalizar_rubro(rubro: str) -> str:
    return rubro.strip().lower()


def get_commodity_variation_pct(symbol: str) -> Optional[float]:
    """Variación % del precio de cierre de `symbol` en los últimos 7
    días, vía la API pública (sin key) de Yahoo Finance. Cache 12h."""

    def _fetch():
        resp = httpx.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range": "7d", "interval": "1d"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        resp.raise_for_status()
        result = resp.json()["chart"]["result"][0]
        closes = [
            c for c in result["indicators"]["quote"][0]["close"] if c is not None
        ]
        if len(closes) < 2:
            return None
        return (closes[-1] - closes[0]) / closes[0] * 100

    return cached(f"commodity:{symbol}", TTL_COMMODITIES, _fetch)


def get_alerta_insumos(rubro: Optional[str]) -> list[AlertaInsumo]:
    """Objetivo B: alerta de compra anticipada. Solo reporta el
    movimiento de precio — no explica la causa ni predice cuánto más
    subirá. Vacío (sin error) si el rubro no tiene mapeo de commodities."""
    if not rubro:
        return []

    commodities = RUBRO_COMMODITIES.get(_normalizar_rubro(rubro))
    if not commodities:
        return []

    alertas: list[AlertaInsumo] = []
    for symbol, nombre in commodities:
        try:
            variacion = get_commodity_variation_pct(symbol)
        except Exception:
            logger.exception("Error obteniendo variación de %s", symbol)
            continue

        if variacion is None or variacion < UMBRAL_ALERTA_PCT:
            continue

        alertas.append(
            AlertaInsumo(
                commodity=nombre,
                variacion_pct_7d=round(variacion, 1),
                mensaje=(
                    f"El precio de {nombre} subió {round(variacion, 1)}% esta semana "
                    "— si compras este insumo regularmente, podría convenirte "
                    "adelantar tu próxima compra."
                ),
            )
        )

    return alertas
