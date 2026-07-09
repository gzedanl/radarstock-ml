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
- `POST /predict` — requiere header `X-Internal-Token`.
- `GET /internal/check-alerts` — requiere header `X-Internal-Token`.

## Deploy

Incluye un `Dockerfile` simple, pensado para cualquier PaaS con soporte
Docker (no Railway). Variables de entorno requeridas: ver `.env.example`.

En Render (free tier) el servicio se duerme tras ~15 min sin tráfico y
tarda 50+ segundos en despertar — más que el timeout de 8s del frontend
al llamar `/predict`. `.github/workflows/keep-alive.yml` pinguea
`/health` cada 10 min para evitarlo.
