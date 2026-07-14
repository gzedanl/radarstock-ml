import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from services.demand_adjustments import apply_demand_adjustments
from services.ensemble import predict_smart
from services.market_signals import get_alerta_insumos

logger = logging.getLogger(__name__)


def run_prediction_job(
    product_id: str,
    sku: str,
    ventas_historicas: list[float],
    stock_actual: float,
    fechas: Optional[list[str]],
    modelo: str,
    rubro: Optional[str],
    comuna: Optional[str],
) -> None:
    """Ejecutado por el worker RQ (proceso separado, fuera del request
    HTTP de /predict). Escribe el resultado directo en Supabase — el
    dashboard lo recoge en su próxima carga, igual que hoy cuando una
    predicción queda "no actualizada" mientras se recalcula."""
    result = predict_smart(sku, ventas_historicas, stock_actual, fechas, modelo)
    result = apply_demand_adjustments(result, rubro, comuna)
    result.alerta_insumos = get_alerta_insumos(rubro)

    _save_prediction(
        product_id=product_id,
        dias_hasta_quiebre=result.dias_hasta_quiebre,
        cantidad_sugerida=result.cantidad_sugerida,
    )


def _save_prediction(
    product_id: str,
    dias_hasta_quiebre: Optional[int],
    cantidad_sugerida: int,
) -> None:
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY no configuradas — el "
            "worker no puede guardar la predicción."
        )

    resp = httpx.post(
        f"{supabase_url}/rest/v1/predictions",
        params={"on_conflict": "product_id"},
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        json=[
            {
                "product_id": product_id,
                "dias_hasta_quiebre": dias_hasta_quiebre,
                "cantidad_sugerida": cantidad_sugerida,
                "escenario": "base",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        timeout=10,
    )
    resp.raise_for_status()
