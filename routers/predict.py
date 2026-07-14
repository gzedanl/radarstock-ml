from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from rq import Retry

from models.schemas import PredictQueuedResponse, PredictRequest, PredictResponse
from services.auth import verify_internal_token
from services.demand_adjustments import apply_demand_adjustments
from services.ensemble import predict_smart
from services.market_signals import get_alerta_insumos
from services.prediction_job import run_prediction_job
from services.queue import get_queue

router = APIRouter()


@router.post(
    "/predict",
    dependencies=[Depends(verify_internal_token)],
    responses={
        200: {"model": PredictResponse},
        202: {"model": PredictQueuedResponse},
    },
)
def predict(payload: PredictRequest) -> JSONResponse:
    queue = get_queue()

    if queue is not None:
        # Entrenar Prophet/LSTM synchronously dentro del request es lo
        # que satura un solo proceso bajo carga concurrente (ver
        # ensemble.py) — con REDIS_URL configurada, esto se encola y un
        # worker aparte (worker.py) lo procesa y escribe el resultado
        # directo en Supabase.
        job = queue.enqueue(
            run_prediction_job,
            product_id=payload.product_id,
            sku=payload.sku,
            ventas_historicas=payload.ventas_historicas,
            stock_actual=payload.stock_actual,
            fechas=payload.fechas,
            modelo=payload.modelo,
            rubro=payload.rubro,
            comuna=payload.comuna,
            retry=Retry(max=3, interval=[10, 30, 60]),
        )
        return JSONResponse(
            status_code=202,
            content={"status": "queued", "job_id": job.id},
        )

    # Sin cola configurada (ej. desarrollo local sin Redis): procesa
    # síncrono, comportamiento idéntico al de antes de la cola.
    result = predict_smart(
        sku=payload.sku,
        ventas_historicas=payload.ventas_historicas,
        stock_actual=payload.stock_actual,
        fechas=payload.fechas,
        modelo=payload.modelo,
    )
    result = apply_demand_adjustments(result, payload.rubro, payload.comuna)
    result.alerta_insumos = get_alerta_insumos(payload.rubro)

    return JSONResponse(status_code=200, content=result.model_dump())
