import logging
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

from services.cache import cached

logger = logging.getLogger(__name__)

TTL_INDICADORES = 24 * 3600
TTL_FERIADOS = 24 * 3600
TTL_CLIMA = 6 * 3600


def get_indicadores_economicos() -> Optional[dict]:
    """UF, dólar observado e IPC del mes más reciente, vía mindicador.cl
    (API pública chilena, sin key). Cache 24h."""

    def _fetch():
        resp = httpx.get("https://mindicador.cl/api", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {
            "uf": data.get("uf", {}).get("valor"),
            "dolar": data.get("dolar", {}).get("valor"),
            "ipc": data.get("ipc", {}).get("valor"),
        }

    return cached("indicadores_economicos", TTL_INDICADORES, _fetch)


def get_feriados_proximos(dias: int = 14) -> list[str]:
    """Feriados chilenos dentro de los próximos `dias` días, vía la API
    pública del gobierno de Chile (apis.digital.gob.cl). Cache 24h."""

    def _fetch():
        year = date.today().year
        resp = httpx.get(f"https://apis.digital.gob.cl/fl/feriados/{year}", timeout=5)
        resp.raise_for_status()
        feriados = resp.json()

        hoy = date.today()
        limite = hoy + timedelta(days=dias)
        proximos = []
        for f in feriados:
            try:
                fecha = datetime.strptime(f["fecha"], "%Y-%m-%d").date()
            except (KeyError, ValueError, TypeError):
                continue
            if hoy <= fecha <= limite:
                proximos.append(f["fecha"])
        return proximos

    result = cached("feriados_proximos", TTL_FERIADOS, _fetch)
    return result if result is not None else []


def _geocode_comuna(comuna: str) -> Optional[tuple[float, float]]:
    def _fetch():
        resp = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": comuna, "count": 1, "country": "CL"},
            timeout=5,
        )
        resp.raise_for_status()
        results = resp.json().get("results")
        if not results:
            return None
        return (results[0]["latitude"], results[0]["longitude"])

    return cached(f"geocode:{comuna.lower()}", TTL_FERIADOS, _fetch)


def get_weather_forecast(comuna: str) -> Optional[dict]:
    """Pronóstico a 14 días para la comuna, vía Open-Meteo (gratis, sin
    API key). Cache 6h. Devuelve None si la comuna no se pudo geolocalizar
    o si la API falla — nunca lanza excepción."""

    def _fetch():
        coords = _geocode_comuna(comuna)
        if not coords:
            return None
        lat, lon = coords
        resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,precipitation_probability_max",
                "forecast_days": 14,
                "timezone": "America/Santiago",
            },
            timeout=5,
        )
        resp.raise_for_status()
        daily = resp.json().get("daily", {})
        temps = daily.get("temperature_2m_max", [])
        rain = daily.get("precipitation_probability_max", [])
        if not temps:
            return None
        return {
            "temp_max_avg": sum(temps) / len(temps),
            "temp_max_pico": max(temps),
            "prob_lluvia_max": max(rain) if rain else 0,
        }

    return cached(f"clima:{comuna.lower()}", TTL_CLIMA, _fetch)
