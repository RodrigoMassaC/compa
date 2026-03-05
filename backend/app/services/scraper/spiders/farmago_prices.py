"""
farmago_prices.py
Fase B del spider de Farmago: recorre los registros de productos_crudos
que ya tienen url_origen, visita cada URL con Playwright, extrae el precio
actual y lo inserta en historial_precios.

Uso directo:
    docker compose exec compa-api python -c "
    from app.services.scraper.spiders.farmago_prices import FarmagoPriceSpider
    import asyncio
    asyncio.run(FarmagoPriceSpider().run())
    "
"""
import asyncio
import re
import logging
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from playwright.async_api import async_playwright
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.schemas.scraper_schema import ScrapedProduct
from app.services.scraper.base_spider import BaseSpider


# JavaScript que extrae el precio del DOM de Farmago (Odoo eCommerce).
PRICE_JS = """
() => {
    const selectors = [
        '[itemprop="price"]',
        '.oe_currency_value',
        '.h6.mb-0',
        '.product_price .oe_price',
        '#product_details .css_editable_mode_hidden'
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText && el.innerText.trim()) {
            const text = el.innerText.trim();
            if (/[0-9]/.test(text)) return text;
        }
        // Also check content attribute (itemprop="price" uses content)
        if (el && el.getAttribute('content')) {
            return el.getAttribute('content');
        }
    }
    return null;
}
"""


def _parse_precio(raw: str) -> Optional[Decimal]:
    """
    Convierte texto de precio venezolano a Decimal.
    Maneja formatos: '2.813,71', '1309.47', '577.71'
    """
    try:
        limpio = raw.strip()
        # Remove currency symbols and text
        limpio = re.sub(r'[BsVES$\s]', '', limpio)
        limpio = limpio.strip()

        tiene_coma = "," in limpio
        tiene_punto = "." in limpio

        if tiene_coma and tiene_punto:
            # Coma después del último punto → coma es decimal (formato VE)
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
                limpio = ("".join(puntos[:-1]) + "." + puntos[-1]) if len(puntos[-1]) == 2 \
                         else limpio.replace(".", "")
            elif len(puntos) == 2 and len(puntos[1]) == 3:
                limpio = limpio.replace(".", "")

        return Decimal(limpio)
    except (InvalidOperation, Exception):
        return None


class FarmagoPriceSpider(BaseSpider):
    """
    Fase B del spider de Farmago.
    Lee productos_crudos de Farmago con url_origen, extrae el precio
    actual de cada página con Playwright y lo guarda en historial_precios.
    """

    BATCH_SIZE = 10
    DELAY_MIN = 2.0
    DELAY_MAX = 3.5

    async def _get_productos(self) -> list:
        """Retorna filas (id_producto_crudo, url_origen) de Farmago con URL."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("""
                SELECT pc.id_producto_crudo, pc.url_origen
                FROM productos_crudos pc
                JOIN establecimientos e ON e.id_establecimiento = pc.id_establecimiento
                JOIN cadenas_comerciales c ON c.id_cadena = e.id_cadena
                WHERE c.nombre_cadena = 'Farmago'
                  AND pc.url_origen IS NOT NULL
                ORDER BY pc.creado_en DESC
            """))
            return result.fetchall()

    async def _save_precio(self, id_producto_crudo, precio_bruto: Decimal) -> None:
        """Inserta un registro en historial_precios (VES / SCRAPING_WEB)."""
        async with AsyncSessionLocal() as session:
            await session.execute(text("""
                INSERT INTO historial_precios
                    (id_producto_crudo, precio_bruto, moneda_origen, fuente_datos)
                VALUES
                    (:id_crudo, :precio, 'VES', 'SCRAPING_WEB')
            """), {"id_crudo": str(id_producto_crudo), "precio": precio_bruto})
            await session.commit()

    async def _extract_price(self, page, url: str) -> Optional[Decimal]:
        """Visita la URL del producto y extrae el precio con JS evaluation."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(2000)

            precio_raw = await page.evaluate(PRICE_JS)
            if not precio_raw:
                self.logger.warning(f"  ⚠️  Precio no encontrado: {url}")
                return None

            precio = _parse_precio(precio_raw)
            if precio is None:
                self.logger.warning(f"  ⚠️  No se pudo parsear '{precio_raw}' → {url}")
            return precio

        except Exception as e:
            self.logger.error(f"  ❌ Error visitando {url}: {e}")
            return None

    async def run(self) -> List[ScrapedProduct]:
        """Punto de entrada del spider."""
        self.logger.info("🕷️  FarmagoPriceSpider iniciando...")

        productos = await self._get_productos()
        total = len(productos)

        if not total:
            self.logger.warning(
                "⚠️  No hay productos_crudos con url_origen para Farmago. "
                "Ejecuta primero FarmagoSpider."
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
                            self.logger.info(f"  ✅ Bs. {precio:,.2f}  ←  {url}")
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

            await context.close()
            await browser.close()

        self.logger.info(
            f"\n🏁 Spider finalizado — "
            f"✅ Extraídos: {extraidos}  ❌ Fallados: {fallados}  Total: {total}"
        )
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    async def _main():
        spider = FarmagoPriceSpider()
        await spider.run()

    asyncio.run(_main())
