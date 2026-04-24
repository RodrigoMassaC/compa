"""
tasa_bcv.py
Spider que extrae la tasa oficial USD/VES del Banco Central de Venezuela (BCV)
y la guarda en la tabla `historico_tasa_bcv`.

Fuente: https://www.bcv.org.ve/ (página principal tiene la tasa en el bloque
"Tipo de Cambio de Referencia")

Uso:
    from app.services.scraper.spiders.tasa_bcv import actualizar_tasa_bcv
    await actualizar_tasa_bcv()
"""
import logging
import re
import ssl
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx
from sqlalchemy import text

from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

BCV_URL = "https://www.bcv.org.ve/"

# El sitio del BCV tiene cert SSL inestable; aceptamos sin verificación.
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


async def _fetch_bcv_html() -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    async with httpx.AsyncClient(
        headers=headers, timeout=30, verify=_ssl_ctx, follow_redirects=True
    ) as client:
        resp = await client.get(BCV_URL)
        resp.raise_for_status()
        return resp.text


def _parse_tasa_usd(html: str) -> Optional[Decimal]:
    """
    Extrae la tasa USD del HTML de bcv.org.ve.

    El bloque tiene estructura:
    <div id="dolar">
      ...
      <strong>123,4567</strong>
    </div>
    """
    # Primero intentamos con el bloque #dolar
    m = re.search(
        r'id="dolar".*?<strong>\s*([\d.,]+)\s*</strong>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not m:
        # Fallback — cualquier strong con número > 50 (la tasa nunca está por debajo)
        candidatos = re.findall(r"<strong>\s*([\d.,]+)\s*</strong>", html)
        for c in candidatos:
            try:
                val = _normalizar_decimal(c)
                if val and val > Decimal("50"):
                    return val
            except Exception:
                continue
        logger.warning("No se encontró la tasa USD en el HTML del BCV")
        return None

    return _normalizar_decimal(m.group(1))


def _normalizar_decimal(raw: str) -> Optional[Decimal]:
    """Convierte '123,4567' o '1.234,56' a Decimal."""
    s = raw.strip()
    if "," in s and "." in s:
        # formato venezolano: 1.234,56 -> 1234.56
        s = s.replace(".", "").replace(",", ".")
    else:
        # solo coma decimal: 123,45 -> 123.45
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


async def actualizar_tasa_bcv() -> Optional[Decimal]:
    """
    Pipeline completo:
      1. Descarga HTML del BCV.
      2. Parsea tasa USD.
      3. Inserta o actualiza en historico_tasa_bcv para la fecha de hoy.

    Retorna la tasa guardada (Decimal) o None si falló.
    """
    logger.info("🏦 Consultando tasa BCV en %s ...", BCV_URL)
    try:
        html = await _fetch_bcv_html()
    except Exception as e:
        logger.error("Error descargando BCV: %s", e)
        return None

    tasa = _parse_tasa_usd(html)
    if tasa is None:
        logger.error("No se pudo parsear la tasa BCV del HTML")
        return None

    hoy = date.today()
    logger.info("✅ Tasa BCV extraída: %s (fecha %s)", tasa, hoy)

    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                """
                INSERT INTO historico_tasa_bcv (valor_usd, fecha)
                VALUES (:valor, :fecha)
                ON CONFLICT (fecha) DO UPDATE SET valor_usd = EXCLUDED.valor_usd
                """
            ),
            {"valor": tasa, "fecha": hoy},
        )
        await session.commit()

    logger.info("💾 Tasa BCV %s guardada en DB (fecha %s)", tasa, hoy)
    return tasa
