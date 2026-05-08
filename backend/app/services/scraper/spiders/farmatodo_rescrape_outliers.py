"""
Script de re-scraping SELECTIVO de productos con precios outlier en Farmatodo.

Identifica productos cuyo precio actual en Farmatodo es < 30% del mediano del
mismo producto en otras tiendas (probables placeholders mal scrapeados),
visita sus URLs y guarda el precio actualizado (en USD con la nueva lógica).

Uso:
    python -m app.services.scraper.spiders.farmatodo_rescrape_outliers

Tiempo: ~5 min para 50 productos.
"""
import asyncio
import logging
from decimal import Decimal
from typing import List, Optional

from playwright.async_api import async_playwright
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.services.scraper.spiders.farmatodo_prices import (
    FarmatodoPriceSpider,
    PRICE_JS,
    _parse_precio,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger("RescrapeOutliers")


async def obtener_outliers() -> List[tuple]:
    """Retorna lista de (id_producto_crudo, url_origen) de Farmatodo con precio outlier."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            WITH tasa AS (SELECT valor_usd FROM historico_tasa_bcv ORDER BY fecha DESC LIMIT 1),
            precios AS (
                SELECT DISTINCT ON (pc.id_producto_maestro, e.id_cadena)
                    pc.id_producto_maestro,
                    e.id_cadena,
                    c.nombre_cadena,
                    pc.id_producto_crudo,
                    pc.url_origen,
                    CASE
                        WHEN hp.moneda_origen = 'USD' THEN hp.precio_bruto
                        ELSE hp.precio_bruto / (SELECT valor_usd FROM tasa)
                    END AS precio_usd
                FROM productos_crudos pc
                JOIN establecimientos e ON e.id_establecimiento = pc.id_establecimiento
                JOIN cadenas_comerciales c ON c.id_cadena = e.id_cadena
                JOIN historial_precios hp ON hp.id_producto_crudo = pc.id_producto_crudo
                WHERE pc.id_producto_maestro IS NOT NULL
                ORDER BY pc.id_producto_maestro, e.id_cadena, hp.fecha_lectura DESC
            ),
            medianos AS (
                SELECT id_producto_maestro,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY precio_usd) AS mediano,
                       COUNT(*) AS n_tiendas
                FROM precios
                GROUP BY id_producto_maestro
            )
            SELECT p.id_producto_crudo, p.url_origen
            FROM precios p
            JOIN medianos m ON m.id_producto_maestro = p.id_producto_maestro
            WHERE p.nombre_cadena = 'Farmatodo'
              AND m.n_tiendas >= 2
              AND p.precio_usd < m.mediano * 0.30
              AND p.url_origen IS NOT NULL
        """))
        return [(row.id_producto_crudo, row.url_origen) for row in result.fetchall()]


async def main():
    outliers = await obtener_outliers()
    logger.info(f"Productos outlier en Farmatodo: {len(outliers)}")

    if not outliers:
        logger.info("Nada que re-scrapear.")
        return

    spider = FarmatodoPriceSpider()
    extraidos = 0
    fallados = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=spider._get_random_ua(),
            viewport={"width": 1280, "height": 800},
        )

        for id_crudo, url in outliers:
            page = await context.new_page()
            try:
                # Reutilizamos _extract_price del spider (con su parser y filtros)
                precio_bruto = await spider._extract_price(page, url)
                if precio_bruto is None:
                    fallados += 1
                    continue
                # _save_precio convierte VES → USD con tasa BCV
                await spider._save_precio(id_crudo, precio_bruto)
                logger.info(f"  ✅ {url[-60:]} → {precio_bruto} Bs")
                extraidos += 1
            except Exception as e:
                logger.error(f"  ❌ Error {url}: {e}")
                fallados += 1
            finally:
                await page.close()
            # Delay anti-bloqueo más conservador
            await asyncio.sleep(2.5)

        await context.close()
        await browser.close()

    logger.info(
        f"🏁 Re-scraping outliers finalizado — "
        f"✅ {extraidos} actualizados, ❌ {fallados} fallaron, total {len(outliers)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
