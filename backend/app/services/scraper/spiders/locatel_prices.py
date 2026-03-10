"""
Spider de actualización de precios para Locatel Venezuela.
Fase de solo-precios: lee productos ya existentes en productos_crudos
y actualiza historial_precios con los precios actuales.

Útil para:
  - Actualizaciones diarias/semanales de precios sin re-indexar
  - Llenar precios de productos ya existentes en DB
"""
import asyncio
import json
import logging
import re
from decimal import Decimal
from typing import List, Optional

from playwright.async_api import async_playwright
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.services.scraper.base_spider import BaseSpider

LOCATEL_ID_ESTABLECIMIENTO = "e2d24690-b4eb-434d-a191-b79d486ec75b"
BASE_URL = "https://www.locatel.com.ve"


class LocatelPriceSpider(BaseSpider):
    """
    Lee URLs de productos Locatel ya registrados en productos_crudos
    y actualiza historial_precios con los precios actuales.
    """

    def __init__(self, batch_size: int = 50):
        super().__init__()
        self.batch_size = batch_size

    async def run(self) -> List:
        self.logger.info("Iniciando LocatelPriceSpider")
        updated = 0

        async with AsyncSessionLocal() as session:
            q = text("""
                SELECT id_producto_crudo, url_origen, nombre_original
                FROM   productos_crudos
                WHERE  id_establecimiento = :id_est
                  AND  url_origen IS NOT NULL
                ORDER  BY updated_at ASC NULLS FIRST
                LIMIT  :lim
            """)
            result = await session.execute(q, {
                "id_est": LOCATEL_ID_ESTABLECIMIENTO,
                "lim":    self.batch_size,
            })
            productos = result.fetchall()

        self.logger.info(f"Productos a actualizar: {len(productos)}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )

            for id_prod, url, nombre in productos:
                precio = await self._get_precio(context, url)
                if precio and precio > Decimal("0"):
                    await self._insert_precio(id_prod, precio)
                    updated += 1
                    self.logger.info(f"✅ {nombre[:50]} → {precio} VES")
                else:
                    self.logger.warning(f"⚠️  Sin precio: {nombre[:50]}")

            await context.close()
            await browser.close()

        self.logger.info(f"LocatelPriceSpider finalizado. Precios actualizados: {updated}")
        return []

    async def _get_precio(self, context, url: str) -> Optional[Decimal]:
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3000)

            precio_raw = await page.evaluate("""() => {
                const el = document.querySelector('[class*="sellingPrice"]')
                        || document.querySelector('[class*="price"]');
                return el ? el.innerText.trim() : null;
            }""")

            if not precio_raw:
                return None

            return self._parse_precio_ves(precio_raw)
        except Exception as e:
            self.logger.warning(f"Error obteniendo precio de {url}: {e}")
            return None
        finally:
            await page.close()

    def _parse_precio_ves(self, precio_raw: str) -> Decimal:
        try:
            limpio = re.sub(r"Bs\.?S?\.?\s*", "", precio_raw, flags=re.IGNORECASE).strip()
            limpio = re.sub(r"\s+", "", limpio)

            tiene_coma  = "," in limpio
            tiene_punto = "." in limpio

            if tiene_coma and tiene_punto:
                if limpio.rfind(",") > limpio.rfind("."):
                    limpio = limpio.replace(".", "").replace(",", ".")
                else:
                    limpio = limpio.replace(",", "")
            elif tiene_coma:
                partes = limpio.split(",")
                if len(partes) == 2 and len(partes[1]) <= 2:
                    limpio = limpio.replace(",", ".")
                else:
                    limpio = limpio.replace(",", "")
            elif tiene_punto:
                puntos = limpio.split(".")
                if len(puntos) > 2:
                    if len(puntos[-1]) == 2:
                        entero = "".join(puntos[:-1])
                        limpio = f"{entero}.{puntos[-1]}"
                    else:
                        limpio = limpio.replace(".", "")
                elif len(puntos) == 2 and len(puntos[1]) == 3:
                    limpio = limpio.replace(".", "")

            return Decimal(limpio)
        except Exception:
            return Decimal("0.0")

    async def _insert_precio(self, id_producto_crudo, precio: Decimal):
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("""
                    INSERT INTO historial_precios (
                        id_producto_crudo, precio, moneda, fecha_captura
                    ) VALUES (:id_prod, :precio, 'VES', NOW())
                """), {"id_prod": id_producto_crudo, "precio": float(precio)})
                await session.commit()
        except Exception as e:
            self.logger.error(f"Error insertando precio para {id_producto_crudo}: {e}")
