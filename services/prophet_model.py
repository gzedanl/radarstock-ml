from datetime import date, timedelta
from typing import Optional

import pandas as pd
from prophet import Prophet

from models.schemas import Escenarios, PredictResponse

MIN_POINTS = 14
FORECAST_HORIZON_DAYS = 30


class SerieMuyCortaError(Exception):
    """La serie de ventas históricas es demasiado corta para entrenar Prophet."""


def _build_dataframe(
    ventas_historicas: list[float], fechas: Optional[list[str]]
) -> pd.DataFrame:
    if fechas:
        if len(fechas) != len(ventas_historicas):
            raise ValueError("fechas y ventas_historicas deben tener el mismo largo")
        ds = pd.to_datetime(fechas)
    else:
        end = date.today()
        start = end - timedelta(days=len(ventas_historicas) - 1)
        ds = pd.date_range(start=start, end=end)

    return pd.DataFrame({"ds": ds, "y": ventas_historicas})


def _dias_hasta_quiebre(
    stock_actual: float, demanda_diaria: list[float]
) -> Optional[int]:
    remaining = stock_actual
    for i, demanda in enumerate(demanda_diaria):
        remaining -= max(demanda, 0)
        if remaining <= 0:
            return i + 1
    return None


def predict_with_prophet(
    sku: str,
    ventas_historicas: list[float],
    stock_actual: float,
    fechas: Optional[list[str]] = None,
) -> PredictResponse:
    if len(ventas_historicas) < MIN_POINTS:
        raise SerieMuyCortaError(
            f"Se requieren al menos {MIN_POINTS} puntos históricos para Prophet "
            f"(se recibieron {len(ventas_historicas)})."
        )

    df = _build_dataframe(ventas_historicas, fechas)

    model = Prophet()
    model.fit(df)

    future = model.make_future_dataframe(periods=FORECAST_HORIZON_DAYS)
    forecast = model.predict(future)
    future_forecast = forecast.tail(FORECAST_HORIZON_DAYS)

    # yhat_upper (más demanda) = escenario optimista de ventas,
    # yhat_lower (menos demanda) = escenario pesimista de ventas.
    base_demand = future_forecast["yhat"].clip(lower=0).tolist()
    optimista_demand = future_forecast["yhat_upper"].clip(lower=0).tolist()
    pesimista_demand = future_forecast["yhat_lower"].clip(lower=0).tolist()

    dias_hasta_quiebre = _dias_hasta_quiebre(stock_actual, base_demand)

    return PredictResponse(
        sku=sku,
        dias_hasta_quiebre=dias_hasta_quiebre,
        cantidad_sugerida=round(sum(base_demand)),
        escenarios=Escenarios(
            base=round(sum(base_demand)),
            optimista=round(sum(optimista_demand)),
            pesimista=round(sum(pesimista_demand)),
        ),
        modelo_usado="prophet",
        alerta_insumos=[],
    )
