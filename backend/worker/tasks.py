"""
Tareas Celery de Compa.
Incluye la tarea CRON que descarga la tasa BCV diariamente.

Regla de arquitectura: NUNCA hacer UPDATE en historico_tasa_bcv, solo INSERT.
"""
import asyncio
import logging
from datetime import date, datetime
from decimal import Decimal

import httpx
import asyncpg
from bs4 import BeautifulSoup

from worker.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


def _parse_bcv_rate(html: str) -> Decimal | None:
    """
    Extrae la tasa USD del HTML de la página del BCV.
    La tasa se publica en <div id="dolar"> dentro de la sección de tasas.
    """
    soup = BeautifulSoup(html, "lxml")

    # Buscar el bloque de tasa del dólar en la página del BCV
    dolar_block = soup.find("div", {"id": "dolar"})
    if not dolar_block:
        # Intento alternativo: buscar el valor en tabla de tasas
        dolar_block = soup.find("strong", string=lambda t: t and "USD" in t)

    if dolar_block:
        # El valor numérico suele estar en <strong> dentro del bloque
        strong_tag = dolar_block.find("strong")
        if strong_tag:
            raw_value = strong_tag.get_text(strip=True)
            # El BCV usa coma como separador decimal: "36,45" → "36.45"
            normalized = raw_value.replace(",", ".").strip()
            try:
                return Decimal(normalized)
            except Exception:
                pass

    logger.warning("No se pudo extraer la tasa BCV del HTML recibido.")
    return None


async def _save_rate_async(valor_usd: Decimal) -> None:
    """
    Guarda la tasa BCV en historico_tasa_bcv usando asyncpg.
    Solo INSERT — nunca UPDATE (regla de arquitectura #1).
    """
    raw_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(raw_url)
    try:
        today = date.today()
        await conn.execute(
            """
            INSERT INTO historico_tasa_bcv (fecha, valor_usd, fuente)
            VALUES ($1, $2, 'BCV')
            ON CONFLICT (fecha) DO NOTHING
            """,
            today,
            valor_usd,
        )
        logger.info(f"Tasa BCV guardada: {today} → {valor_usd} USD/VES")
    finally:
        await conn.close()


@celery_app.task(
    name="worker.tasks.fetch_bcv_rate",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # Reintentar en 5 minutos si falla
)
def fetch_bcv_rate(self) -> dict:
    """
    Descarga la tasa oficial USD/VES del BCV y la guarda en historico_tasa_bcv.
    Se ejecuta diariamente a las 6:00 AM hora de Caracas (10:00 AM UTC).
    """
    bcv_url = "https://www.bcv.org.ve/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; CompaBot/1.0; "
            "+https://compa.com.ve/bot)"
        )
    }

    try:
        logger.info(f"[BCV] Iniciando descarga de tasa — {datetime.utcnow()}")

        # Obtener la página del BCV de forma síncrona (Celery no es async)
        with httpx.Client(timeout=30, headers=headers) as client:
            response = client.get(bcv_url)
            response.raise_for_status()

        # Parsear la tasa del HTML
        valor_usd = _parse_bcv_rate(response.text)
        if valor_usd is None:
            raise ValueError("No se pudo extraer la tasa BCV del HTML.")

        # Guardar en la DB usando asyncpg en un loop async temporal
        asyncio.run(_save_rate_async(valor_usd))

        resultado = {
            "fecha": str(date.today()),
            "valor_usd": str(valor_usd),
            "fuente": "BCV",
        }
        logger.info(f"[BCV] Tasa guardada: {resultado}")
        return resultado

    except Exception as exc:
        logger.error(f"[BCV] Error al obtener tasa: {exc}")
        # Reintentar automáticamente hasta 3 veces
        raise self.retry(exc=exc)
