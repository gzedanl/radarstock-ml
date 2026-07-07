import logging
from typing import Optional

from models.schemas import Escenarios, PredictResponse
from services.external_data import get_feriados_proximos, get_weather_forecast

logger = logging.getLogger(__name__)

# Heurísticas simples y documentadas — no pretenden ser precisas, solo
# capturar señales obvias de estacionalidad/clima. Objetivo A únicamente
# (ajustar demanda proyectada); no tiene relación con alerta_insumos
# (objetivo B, en market_signals.py).
AJUSTE_FERIADO_ESTACIONAL = 1.05  # +5% antes de fiestas patrias/navidad
AJUSTE_CLIMA = 1.08  # +8% si el clima extremo favorece la demanda del rubro
TEMP_EXTREMA_C = 30.0

RUBROS_SENSIBLES_CLIMA = {"bebidas", "ropa", "ferreteria"}

# MM-DD de fechas estacionales: fiestas patrias (18-19 sep) y navidad.
FERIADOS_ESTACIONALES_MMDD = {"09-18", "09-19", "12-25"}


def _scale_response(response: PredictResponse, factor: float) -> PredictResponse:
    return response.model_copy(
        update={
            "cantidad_sugerida": round(response.cantidad_sugerida * factor),
            "escenarios": Escenarios(
                base=round(response.escenarios.base * factor),
                optimista=round(response.escenarios.optimista * factor),
                pesimista=round(response.escenarios.pesimista * factor),
            ),
        }
    )


def apply_demand_adjustments(
    response: PredictResponse, rubro: Optional[str], comuna: Optional[str]
) -> PredictResponse:
    factor = 1.0

    try:
        feriados = get_feriados_proximos(dias=14)
        if any(fecha[5:] in FERIADOS_ESTACIONALES_MMDD for fecha in feriados):
            factor *= AJUSTE_FERIADO_ESTACIONAL
    except Exception:
        logger.exception("No se pudo evaluar el ajuste de feriados")

    try:
        rubro_normalizado = rubro.strip().lower() if rubro else None
        if rubro_normalizado in RUBROS_SENSIBLES_CLIMA and comuna:
            clima = get_weather_forecast(comuna)
            if clima and clima.get("temp_max_pico", 0) >= TEMP_EXTREMA_C:
                factor *= AJUSTE_CLIMA
    except Exception:
        logger.exception("No se pudo evaluar el ajuste de clima")

    if factor == 1.0:
        return response

    return _scale_response(response, factor)
