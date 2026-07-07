from fastapi import APIRouter, Depends, HTTPException, Query, status

from models.schemas import AlertaStock
from services.alerts import check_alerts
from services.auth import verify_internal_token

router = APIRouter()


@router.get(
    "/internal/check-alerts",
    response_model=list[AlertaStock],
    dependencies=[Depends(verify_internal_token)],
)
def get_check_alerts(umbral_dias: int = Query(default=7, ge=1)) -> list[AlertaStock]:
    try:
        return check_alerts(umbral_dias=umbral_dias)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
