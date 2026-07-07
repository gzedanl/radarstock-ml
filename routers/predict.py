from fastapi import APIRouter, Depends

from models.schemas import PredictRequest, PredictResponse
from services.auth import verify_internal_token
from services.demand_adjustments import apply_demand_adjustments
from services.ensemble import predict_smart
from services.market_signals import get_alerta_insumos

router = APIRouter()


@router.post(
    "/predict",
    response_model=PredictResponse,
    dependencies=[Depends(verify_internal_token)],
)
def predict(payload: PredictRequest) -> PredictResponse:
    result = predict_smart(
        sku=payload.sku,
        ventas_historicas=payload.ventas_historicas,
        stock_actual=payload.stock_actual,
        fechas=payload.fechas,
        modelo=payload.modelo,
    )

    # Objetivo A: ajusta la demanda proyectada (feriados/clima).
    result = apply_demand_adjustments(result, payload.rubro, payload.comuna)

    # Objetivo B: alerta de compra anticipada de insumos, independiente
    # del ajuste de demanda de arriba.
    result.alerta_insumos = get_alerta_insumos(payload.rubro)

    return result
