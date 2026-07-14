from typing import Literal, Optional

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    # Fila de destino en `predictions` (tabla de radarstock). La necesita
    # el worker de la cola para saber dónde escribir el resultado cuando
    # /predict responde 202 en vez de calcular síncrono — ver
    # services/prediction_job.py.
    product_id: str
    sku: str
    # Ventas diarias históricas, en orden cronológico (la última entrada
    # es el día más reciente).
    ventas_historicas: list[float]
    # Fechas correspondientes a ventas_historicas (mismo largo), formato
    # YYYY-MM-DD. Si no se envían, se asumen días consecutivos terminando hoy.
    fechas: Optional[list[str]] = None
    stock_actual: float = 0
    modelo: Literal["prophet", "lstm", "ensemble"] = "ensemble"
    # Contexto opcional para ajustes de demanda y alertas de insumos
    # (Fase 3.4). Sin esto, esos ajustes simplemente no se aplican.
    rubro: Optional[str] = None
    comuna: Optional[str] = None


class Escenarios(BaseModel):
    base: int
    optimista: int
    pesimista: int


class AlertaInsumo(BaseModel):
    commodity: str
    variacion_pct_7d: float
    mensaje: str


class PredictResponse(BaseModel):
    sku: str
    dias_hasta_quiebre: Optional[int]
    cantidad_sugerida: int
    escenarios: Escenarios
    modelo_usado: str
    alerta_insumos: list[AlertaInsumo] = Field(default_factory=list)


class PredictQueuedResponse(BaseModel):
    """Respuesta de /predict cuando hay una cola configurada (REDIS_URL):
    no calcula síncrono, encola el job y confirma que se aceptó. El
    resultado real lo escribe el worker directo en Supabase."""

    status: Literal["queued"]
    job_id: str


class AlertaStock(BaseModel):
    sku: str
    company_id: str
    dias_hasta_quiebre: int
    cantidad_sugerida: int
    nivel: Literal["critico", "alto"]
