import hashlib
import json
import logging
from typing import Optional

from models.schemas import Escenarios, PredictResponse
from services.cache import cached
from services.lstm_model import LSTMNoDisponibleError, predict_with_lstm
from services.prophet_model import SerieMuyCortaError, predict_with_prophet
from services.simple_predict import predict_simple

logger = logging.getLogger(__name__)

# Entrenar Prophet y/o LSTM desde cero es el costo real de /predict (varios
# segundos de CPU por SKU). Cachear por input evita reentrenar cuando el
# mismo SKU se vuelve a pedir con los mismos datos poco después — reintentos
# tras un timeout del lado de Next.js, o un "recalcular" manual justo
# después de subir el CSV. Si ventas_historicas cambia, la key cambia y se
# reentrena — nunca sirve una predicción calculada con datos viejos.
TTL_PREDICTION_SECONDS = 6 * 3600


def _prediction_cache_key(
    sku: str,
    ventas_historicas: list[float],
    stock_actual: float,
    fechas: Optional[list[str]],
    modelo: str,
) -> str:
    payload = json.dumps(
        {"v": ventas_historicas, "s": stock_actual, "f": fechas, "m": modelo},
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"predict:{sku}:{digest}"


def _avg_optional(a: Optional[int], b: Optional[int]) -> Optional[int]:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return round((a + b) / 2)


def _combine(a: PredictResponse, b: PredictResponse) -> PredictResponse:
    return PredictResponse(
        sku=a.sku,
        dias_hasta_quiebre=_avg_optional(a.dias_hasta_quiebre, b.dias_hasta_quiebre),
        cantidad_sugerida=round((a.cantidad_sugerida + b.cantidad_sugerida) / 2),
        escenarios=Escenarios(
            base=round((a.escenarios.base + b.escenarios.base) / 2),
            optimista=round((a.escenarios.optimista + b.escenarios.optimista) / 2),
            pesimista=round((a.escenarios.pesimista + b.escenarios.pesimista) / 2),
        ),
        modelo_usado="ensemble",
        alerta_insumos=[],
    )


def predict_smart(
    sku: str,
    ventas_historicas: list[float],
    stock_actual: float,
    fechas: Optional[list[str]],
    modelo: str,
) -> PredictResponse:
    """Envoltorio con cache sobre _predict_smart_uncached — ver
    TTL_PREDICTION_SECONDS arriba para el motivo."""
    key = _prediction_cache_key(sku, ventas_historicas, stock_actual, fechas, modelo)
    return cached(
        key,
        TTL_PREDICTION_SECONDS,
        lambda: _predict_smart_uncached(
            sku, ventas_historicas, stock_actual, fechas, modelo
        ),
    )


def _predict_smart_uncached(
    sku: str,
    ventas_historicas: list[float],
    stock_actual: float,
    fechas: Optional[list[str]],
    modelo: str,
) -> PredictResponse:
    """Nunca deja caer el request: si el modelo pedido (o alguno de los
    que componen el ensemble) no está disponible para esta serie, cae
    al modelo más simple que sí lo esté. `modelo_usado` siempre refleja
    lo que realmente se usó, no lo pedido."""

    prophet_result: Optional[PredictResponse] = None
    lstm_result: Optional[PredictResponse] = None

    if modelo in ("prophet", "ensemble"):
        try:
            prophet_result = predict_with_prophet(
                sku, ventas_historicas, stock_actual, fechas
            )
        except SerieMuyCortaError as exc:
            logger.warning("Prophet no disponible para %s: %s", sku, exc)
        except Exception:
            logger.exception("Prophet falló inesperadamente para %s", sku)

    if modelo in ("lstm", "ensemble"):
        try:
            lstm_result = predict_with_lstm(sku, ventas_historicas, stock_actual)
        except LSTMNoDisponibleError as exc:
            logger.warning("LSTM no disponible para %s: %s", sku, exc)
        except Exception:
            logger.exception("LSTM falló inesperadamente para %s", sku)

    if modelo == "ensemble" and prophet_result and lstm_result:
        return _combine(prophet_result, lstm_result)

    if prophet_result:
        return prophet_result
    if lstm_result:
        return lstm_result

    logger.warning(
        "Cayendo a modelo simple para %s: sin suficiente data para Prophet/LSTM", sku
    )
    return predict_simple(sku, ventas_historicas, stock_actual)
