"""
Spider para Central Madeirense Venezuela — Fase A (índice).
Usa httpx + BeautifulSoup (sin Playwright) ya que WooCommerce sirve el HTML estático.
"""
import asyncio
import random
from decimal import Decimal
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

from app.core.database import AsyncSessionLocal
from app.schemas.scraper_schema import ScrapedProduct
from app.services.scraper.base_spider import BaseSpider

BASE_URL = "https://tucentralonline.com"
SHOP_BASE_URL = f"{BASE_URL}/La-Alameda-50/comprar"

CATEGORIAS = [
    "viveres",
    "refrigerados",
    "fruteria-y-vegetales",
    "cuidado-personal",
    "articulos-de-limpieza",
    "licores",
    "hogar-temporada",
]

PRODUCTS_PER_PAGE = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-VE,es;q=0.9",
}


class CentralMadeirenSeSpider(BaseSpider):

    DELAY_MIN: float = 1.5
    DELAY_MAX: float = 2.5

    async def run(self) -> List[ScrapedProduct]:
        self.logger.info("Iniciando CentralMadeirenSeSpider")
        scraped_products: List[ScrapedProduct] = []

        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            for categoria in CATEGORIAS:
                self.logger.info(f"📂 Categoría: {categoria}")
                page_num = 1

                while True:
                    url = f"{SHOP_BASE_URL}/{categoria}/page/{page_num}/"
                    self.logger.info(f"Página: {url}")

                    try:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        soup = BeautifulSoup(resp.text, "lxml")
                        blocks = soup.select("li.product")

                        if not blocks:
                            self.logger.info(f"Sin productos en {categoria} p{page_num}, fin de categoría.")
                            break

                        for block in blocks:
                            product = self._parse_block(block)
                            if product:
                                scraped_products.append(product)
                                await self._save_to_db(product)

                        self.logger.info(f"{categoria} p{page_num}: {len(blocks)} productos. Total: {len(scraped_products)}")

                        if len(blocks) < PRODUCTS_PER_PAGE:
                            break

                        page_num += 1
                        await asyncio.sleep(random.uniform(self.DELAY_MIN, self.DELAY_MAX))

                    except Exception as e:
                        self.logger.error(f"Error en {url}: {e}")
                        break

        self.logger.info(f"Finalizado. Total: {len(scraped_products)}")
        return scraped_products

    def _parse_block(self, block) -> Optional[ScrapedProduct]:
        try:
            nombre_tag = block.select_one(".woocommerce-loop-product__title")
            nombre = nombre_tag.get_text(strip=True) if nombre_tag else None
            if not nombre:
                return None

            link_tag = block.select_one("a.woocommerce-LoopProduct-link") or block.select_one("a[href]")
            url_producto = None
            if link_tag:
                href = link_tag.get("href", "")
                url_producto = href if href.startswith("http") else f"{BASE_URL}{href}"

            sku = url_producto.replace(BASE_URL, "").strip("/") if url_producto else nombre

            return ScrapedProduct(
                nombre_original=nombre,
                precio_bruto=Decimal("0.01"),
                moneda_origen="USD",
                sku_comercio=sku,
                url_origen=url_producto or SHOP_BASE_URL,
            )
        except Exception as e:
            self.logger.warning(f"Error parseando bloque: {e}")
            return None

    async def _save_to_db(self, product: ScrapedProduct) -> None:
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import text

                q_est = text("""
                    SELECT e.id_establecimiento
                    FROM establecimientos e
                    JOIN cadenas_comerciales c ON c.id_cadena = e.id_cadena
                    WHERE c.nombre_cadena = 'Central Madeirense'
                    LIMIT 1
                """)
                result = await session.execute(q_est)
                row = result.fetchone()
                id_est = row[0] if row else None

                if not id_est:
                    self.logger.error("No se encontró establecimiento 'Central Madeirense'")
                    return

                q_insert = text("""
                    INSERT INTO productos_crudos (
                        id_establecimiento, nombre_original, sku_comercio, url_origen, estado_mapeo
                    ) VALUES (:id_est, :nombre, :sku, :url, 'PENDIENTE')
                    ON CONFLICT (id_establecimiento, sku_comercio)
                    DO UPDATE SET
                        nombre_original = EXCLUDED.nombre_original,
                        url_origen = EXCLUDED.url_origen
                """)

                await session.execute(q_insert, {
                    "id_est": id_est,
                    "nombre": product.nombre_original,
                    "sku": product.sku_comercio,
                    "url": product.url_origen,
                })
                await session.commit()
                self.logger.debug(f"💾 {product.nombre_original}")

        except Exception as e:
            self.logger.error(f"Error guardando '{product.nombre_original}': {e}")
