"""
gama_prices.py
Spider de precios para Excelsior Gama (gamaenlinea.com).

Recorre productos_crudos de Gama con url_origen, visita cada URL con
Playwright, extrae el precio actual y lo guarda en historial_precios.

Diferencias con catalog spider:
- Solo visita productos que YA están en DB (no descubre nuevos)
- Filtra los productos sin precio registrado para evitar reprocesos masivos
- Concurrencia secuencial con delays anti-bloqueo

Uso:
    from app.services.scraper.spiders.gama_prices import GamaPriceSpider
    spider = GamaPriceSpider()
    await spider.run()
"""
import re
import logging
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.schemas.scraper_schema import ScrapedProduct
from app.services.scraper.base_spider import BaseSpider


# JS para extraer precio USD del DOM SAP Commerce de Gama
PRICE_JS = """
() => {
    const el = document.querySelector('[class*="price"]')
            || document.querySelector('.price')
            || document.querySelector('cx-product-price');
    return el ? el.innerText.trim() : null;
}
"""


def _parse_precio_usd(precio_raw: str) -> Optional[Decimal]:
    """
    Parsea precios en formato Gama/SAP Hybris.
    Ejemplos: 'Total Ref. 3,75' → 3.75
              'Ref. 12,50'      → 12.50
              'Total Ref. 3.75' → 3.75
    """
    try:
        limpio = re.sub(r"Total|Ref\.|Ref|[\s]", "", precio_raw, flags=re.IGNORECASE).strip()
        if "," in limpio:
            limpio = limpio.replace(".", "").replace(",", ".")
        return Decimal(limpio)
    except (InvalidOperation, ValueError, AttributeError):
        return None


class GamaPriceSpider(BaseSpider):
    """
    Spider de precios para Excelsior Gama.
    Lee productos_crudos con url_origen y refresca el precio en historial_precios.
    """

    BATCH_SIZE = 10
    DELAY_MIN = 2.0
    DELAY_MAX = 4.0
    PAUSA_CADA_N = 100   # pausa cada 100 productos
    PAUSA_SEGUNDOS = 30  # 30s para no estresar el servidor

    # ── Helpers de datos ─────────────────────────────────────────────────────

    async def _get_productos(self) -> list:
        """Productos de Gama con url_origen, priorizando los que NO tienen
        precio registrado. Si quedan, también vuelve a procesar los que sí
        tienen para refrescar (los más antiguos primero).
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("""
                SELECT pc.id_producto_crudo, pc.url_origen
                FROM productos_crudos pc
                JOIN establecimientos e ON e.id_establecimiento = pc.id_establecimiento
                JOIN cadenas_comerciales c ON c.id_cadena = e.id_cadena
                LEFT JOIN LATERAL (
                    SELECT MAX(fecha_lectura) AS ultima
                    FROM historial_precios
                    WHERE id_producto_crudo = pc.id_producto_crudo
                ) hp ON TRUE
                WHERE c.nombre_cadena = 'Excelsior Gama'
                  AND pc.url_origen IS NOT NULL
                ORDER BY hp.ultima ASC NULLS FIRST, pc.creado_en DESC
            """))
            return result.fetchall()

    async def _save_precio(self, id_producto_crudo, precio_bruto: Decimal) -> None:
        """Inserta un registro en historial_precios (USD / SCRAPING_WEB)."""
        async with AsyncSessionLocal() as session:
            await session.execute(text("""
                INSERT INTO historial_precios
                    (id_producto_crudo, precio_bruto, moneda_origen, fuente_datos)
                VALUES
                    (:id_crudo, :precio, 'USD', 'SCRAPING_WEB')
            """), {"id_crudo": str(id_producto_crudo), "precio": precio_bruto})
            await session.commit()

    # ── Extracción Playwright ────────────────────────────────────────────────

    async def _extract_price(self, page, url: str) -> Optional[Decimal]:
        """Visita la URL del producto y extrae el precio USD."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3500)   # SAP CX delay

            precio_raw = await page.evaluate(PRICE_JS)
            if not precio_raw:
                self.logger.warning(f"  ⚠️  Precio no encontrado: {url}")
                return None

            precio = _parse_precio_usd(precio_raw)
            if precio is None:
                self.logger.warning(f"  ⚠️  No se pudo parsear '{precio_raw}' → {url}")
            return precio

        except Exception as e:
            self.logger.error(f"  ❌ Error visitando {url}: {e}")
            return None

    # ── Runner principal ─────────────────────────────────────────────────────

    async def run(self) -> List[ScrapedProduct]:
        """Punto de entrada del spider."""
        self.logger.info("🕷️  GamaPriceSpider iniciando...")

        productos = await self._get_productos()
        total = len(productos)

        if not total:
            self.logger.warning(
                "⚠️  No hay productos_crudos con url_origen para Excelsior Gama. "
                "Ejecuta primero GamaIndexSpider + GamaDetailSpider."
            )
            return []

        self.logger.info(f"📋 Total productos a procesar: {total}")

        extraidos = 0
        fallados = 0
        ua = self._get_random_ua()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=ua,
                viewport={"width": 1280, "height": 800},
            )

            num_lotes = (total + self.BATCH_SIZE - 1) // self.BATCH_SIZE

            for lote_idx in range(num_lotes):
                lote = productos[lote_idx * self.BATCH_SIZE:(lote_idx + 1) * self.BATCH_SIZE]
                self.logger.info(f"\n📦 Lote {lote_idx + 1}/{num_lotes} ({len(lote)} productos)")

                for row in lote:
                    id_crudo, url = row[0], row[1]
                    page = await context.new_page()
                    try:
                        precio = await self._extract_price(page, url)
                        if precio is not None:
                            await self._save_precio(id_crudo, precio)
                            self.logger.info(f"  ✅ ${precio} USD ← {url}")
                            extraidos += 1
                        else:
                            fallados += 1
                    except Exception as e:
                        self.logger.error(f"  ❌ Fallo inesperado [{url}]: {e}")
                        fallados += 1
                    finally:
                        await page.close()

                    await self._random_delay()

                self.logger.info(
                    f"  → Lote {lote_idx + 1} finalizado: "
                    f"✅ {extraidos} extraídos / ❌ {fallados} fallados"
                )

                # Pausa larga cada PAUSA_CADA_N productos
                total_procesado = extraidos + fallados
                if total_procesado > 0 and total_procesado % self.PAUSA_CADA_N == 0:
                    import asyncio
                    self.logger.info(
                        f"⏸️  Pausa anti-bloqueo: {self.PAUSA_SEGUNDOS}s tras {total_procesado} productos..."
                    )
                    await asyncio.sleep(self.PAUSA_SEGUNDOS)

            await context.close()
            await browser.close()

        self.logger.info(
            f"\n🏁 GamaPriceSpider finalizado — "
            f"✅ Extraídos: {extraidos}  ❌ Fallados: {fallados}  Total: {total}"
        )
        return []   # Los precios ya fueron persistidos directamente
