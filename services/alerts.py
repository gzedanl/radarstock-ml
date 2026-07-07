import os

import httpx

from models.schemas import AlertaStock

NIVEL_CRITICO_DIAS = 3


def _fetch_products_with_predictions() -> list[dict]:
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY no están configuradas"
        )

    resp = httpx.get(
        f"{supabase_url}/rest/v1/products",
        params={
            "select": "sku,company_id,stock_actual,predictions(dias_hasta_quiebre,cantidad_sugerida)"
        },
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def check_alerts(umbral_dias: int = 7) -> list[AlertaStock]:
    productos = _fetch_products_with_predictions()

    alertas: list[AlertaStock] = []
    for producto in productos:
        prediction = producto.get("predictions")
        if isinstance(prediction, list):
            prediction = prediction[0] if prediction else None
        if not prediction:
            continue

        dias = prediction.get("dias_hasta_quiebre")
        if dias is None or dias >= umbral_dias:
            continue

        nivel = "critico" if dias < NIVEL_CRITICO_DIAS else "alto"

        alertas.append(
            AlertaStock(
                sku=producto["sku"],
                company_id=producto["company_id"],
                dias_hasta_quiebre=dias,
                cantidad_sugerida=prediction.get("cantidad_sugerida", 0),
                nivel=nivel,
            )
        )

    return alertas
