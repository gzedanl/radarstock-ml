# radarstock-ml

Backend de Machine Learning de RadarStock. Servicio FastAPI independiente
(no vive en el mismo repo que el frontend Next.js) que recibe series de
ventas por SKU y devuelve predicciones de demanda, días hasta quiebre de
stock, y alertas de insumos.

## Stack

- FastAPI + Uvicorn
- Prophet, LSTM (Keras/TensorFlow) y un modelo Ensemble
- Fuentes externas: mindicador.cl (UF/dólar/IPC), feriados chilenos,
  Open-Meteo (clima), APIs de commodities (contexto de mercado)

## Cómo correr local

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env  # y completa INTERNAL_SERVICE_TOKEN
uvicorn main:app --reload --port 8000
```

## Endpoints

- `GET /health` — sin autenticación.
- `POST /predict` — requiere header `X-Internal-Token`. Con `REDIS_URL`
  configurada, encola el job y responde `202` de inmediato en vez de
  esperar el entrenamiento — ver "Cola de predicciones" abajo.
- `GET /internal/check-alerts` — requiere header `X-Internal-Token`.

## Cola de predicciones (escalabilidad)

Entrenar Prophet/LSTM dentro del request de `/predict` es lo que satura
un solo proceso bajo carga concurrente — con varias empresas subiendo
catálogos grandes a la vez, la mayoría de las llamadas terminan
compitiendo por la misma CPU. Con `REDIS_URL` configurada:

1. `/predict` encola el job (`services/queue.py`) y responde `202` sin
   esperar el entrenamiento.
2. Un proceso worker aparte (`python worker.py`) toma jobs de la cola,
   entrena, y escribe el resultado directo en Supabase
   (`services/prediction_job.py`) — el dashboard lo ve en su próxima
   carga, igual que hoy cuando una predicción queda "no actualizada".
3. Escalar el cómputo pesado es correr más instancias de `worker.py` —
   no comparten estado entre sí, cada una toma jobs de la misma cola.

Sin `REDIS_URL` (ej. desarrollo local sin Redis corriendo), `/predict`
calcula síncrono como antes — no rompe el flujo local.

Para correr la cola local:

```bash
redis-server --port 6379          # o el Redis que tengas a mano
export REDIS_URL=redis://localhost:6379
uvicorn main:app --reload --port 8000   # proceso 1: API
python worker.py                        # proceso 2: worker
```

## Deploy

Incluye un `Dockerfile` simple, pensado para cualquier PaaS con soporte
Docker (no Railway). Variables de entorno requeridas: ver `.env.example`.

En Render, esto son **dos servicios** a partir del mismo repo/Dockerfile:
- **Web Service** — start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- **Background Worker** — start command `python worker.py`. Necesita las
  mismas variables (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) más
  `REDIS_URL`, apuntando a un Redis add-on compartido con el Web Service.

Sin el Background Worker desplegado, `/predict` va a encolar jobs que
nadie consume — las predicciones quedan pendientes indefinidamente. Si
todavía no tienes el worker corriendo en producción, no configures
`REDIS_URL` ahí (déjalo vacío) para que siga procesando síncrono.

En Render (free tier) el servicio web se duerme tras ~15 min sin tráfico
y tarda 50+ segundos en despertar — más que el timeout de 8s del
frontend al llamar `/predict`. `.github/workflows/keep-alive.yml`
pinguea `/health` cada 10 min para evitarlo. El Background Worker no
necesita keep-alive (no atiende HTTP, no se duerme igual).
