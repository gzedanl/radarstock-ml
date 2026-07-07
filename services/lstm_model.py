from typing import Optional

import numpy as np

from models.schemas import Escenarios, PredictResponse

MIN_POINTS_LSTM = 30
WINDOW_SIZE = 7
FORECAST_HORIZON_DAYS = 30


class LSTMNoDisponibleError(Exception):
    """No hay suficiente data histórica para entrenar un LSTM."""


def _build_windows(series: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    for i in range(len(series) - window):
        xs.append(series[i : i + window])
        ys.append(series[i + window])
    return np.array(xs), np.array(ys)


def predict_with_lstm(
    sku: str, ventas_historicas: list[float], stock_actual: float
) -> PredictResponse:
    if len(ventas_historicas) < MIN_POINTS_LSTM:
        raise LSTMNoDisponibleError(
            f"Se requieren al menos {MIN_POINTS_LSTM} puntos históricos para LSTM "
            f"(se recibieron {len(ventas_historicas)})."
        )

    # Import perezoso: TensorFlow es pesado (~cientos de MB) y demora en
    # importarse, así que solo se carga si realmente vamos a usar LSTM.
    from tensorflow import keras

    series = np.array(ventas_historicas, dtype="float32")
    max_val = max(float(series.max()), 1.0)
    scaled = series / max_val

    x_train, y_train = _build_windows(scaled, WINDOW_SIZE)
    x_train = x_train.reshape((x_train.shape[0], WINDOW_SIZE, 1))

    model = keras.Sequential(
        [
            keras.layers.Input(shape=(WINDOW_SIZE, 1)),
            keras.layers.LSTM(16),
            keras.layers.Dense(1),
        ]
    )
    model.compile(optimizer="adam", loss="mse")
    model.fit(x_train, y_train, epochs=30, verbose=0)

    # Forecast recursivo: cada predicción alimenta el input del paso siguiente.
    window = list(scaled[-WINDOW_SIZE:])
    forecast_scaled: list[float] = []
    for _ in range(FORECAST_HORIZON_DAYS):
        x_input = np.array(window[-WINDOW_SIZE:], dtype="float32").reshape(
            (1, WINDOW_SIZE, 1)
        )
        next_val = float(model.predict(x_input, verbose=0)[0, 0])
        forecast_scaled.append(next_val)
        window.append(next_val)

    base_demand = [max(v * max_val, 0) for v in forecast_scaled]

    remaining = stock_actual
    dias_hasta_quiebre: Optional[int] = None
    for i, demanda in enumerate(base_demand):
        remaining -= demanda
        if remaining <= 0:
            dias_hasta_quiebre = i + 1
            break

    cantidad_sugerida = round(sum(base_demand))

    return PredictResponse(
        sku=sku,
        dias_hasta_quiebre=dias_hasta_quiebre,
        cantidad_sugerida=cantidad_sugerida,
        # LSTM no tiene intervalos de confianza nativos como Prophet;
        # usamos el mismo ±15% heurístico que el modelo simple/demo.
        escenarios=Escenarios(
            base=cantidad_sugerida,
            optimista=round(cantidad_sugerida * 1.15),
            pesimista=round(cantidad_sugerida * 0.85),
        ),
        modelo_usado="lstm",
        alerta_insumos=[],
    )
