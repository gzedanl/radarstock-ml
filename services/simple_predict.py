from models.schemas import Escenarios, PredictResponse


def predict_simple(
    sku: str, ventas_historicas: list[float], stock_actual: float
) -> PredictResponse:
    """Cálculo simple (sin ML): promedio de ventas diarias proyectado
    hacia adelante. Usado para fijar el contrato en Fase 3.1, y como
    último fallback si Prophet/LSTM fallan en fases posteriores."""
    avg_daily = (
        sum(ventas_historicas) / len(ventas_historicas) if ventas_historicas else 0
    )

    dias_hasta_quiebre = (
        max(0, round(stock_actual / avg_daily)) if avg_daily > 0 else None
    )
    cantidad_sugerida = round(avg_daily * 30)

    return PredictResponse(
        sku=sku,
        dias_hasta_quiebre=dias_hasta_quiebre,
        cantidad_sugerida=cantidad_sugerida,
        escenarios=Escenarios(
            base=cantidad_sugerida,
            optimista=round(avg_daily * 30 * 1.15),
            pesimista=round(avg_daily * 30 * 0.85),
        ),
        modelo_usado="simple",
        alerta_insumos=[],
    )
