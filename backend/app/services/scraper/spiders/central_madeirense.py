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

    # Tope de seguridad por categoría (evita bucles infinitos si la web cambia).
    MAX_PAGES: int = 80
    # Reintentos ante errores transitorios (timeout, 5xx, conexión).
    MAX_RETRIES: int = 4

    async def run(self) -> List[ScrapedProduct]:
        self.logger.info("Iniciando CentralMadeirenSeSpider")
        scraped_products: List[ScrapedProduct] = []

        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            for categoria in CATEGORIAS:
                self.logger.info(f"📂 Categoría: {categoria}")
                page_num = 1
                seen_skus: set[str] = set()

                while page_num <= self.MAX_PAGES:
                    url = f"{SHOP_BASE_URL}/{categoria}/page/{page_num}/"

                    resp = None
                    end_of_category = False
                    for intento in range(1, self.MAX_RETRIES + 1):
                        try:
                            resp = await client.get(url)
                            # 404 = no existe esa página → fin natural de la categoría
                            if resp.status_code == 404:
                                end_of_category = True
                                break
                            resp.raise_for_status()
                            break
                        except Exception as e:
                            if intento >= self.MAX_RETRIES:
                                self.logger.error(
                                    f"Error persistente en {url} tras {intento} intentos: {e}. "
                                    f"Continuo con siguiente categoría."
                                )
                                resp = None
                                break
                            espera = 2.0 * intento
                            self.logger.warning(
                                f"Error transitorio en {url} (intento {intento}/{self.MAX_RETRIES}): {e}. "
                                f"Reintento en {espera:.0f}s."
                            )
                            await asyncio.sleep(espera)

                    if end_of_category:
                        self.logger.info(f"{categoria}: HTTP 404 en p{page_num}, fin de categoría.")
                        break
                    if resp is None:
                        # Falló tras todos los reintentos → abandonar esta categoría
                        break

                    soup = BeautifulSoup(resp.text, "lxml")
                    blocks = soup.select("li.product")

                    if not blocks:
                        self.logger.info(f"Sin productos en {categoria} p{page_num}, fin de categoría.")
                        break

                    nuevos = 0
                    for block in blocks:
                        product = self._parse_block(block)
                        if not product:
                            continue
                        # Anti-duplicado: si una página repite SKUs ya vistos
                        # (overflow que redirige a página 1) se corta el bucle.
                        if product.sku_comercio in seen_skus:
                            continue
                        seen_skus.add(product.sku_comercio)
                        nuevos += 1
                        scraped_products.append(product)
                        await self._save_to_db(product)

                    self.logger.info(
                        f"{categoria} p{page_num}: {len(blocks)} bloques, {nuevos} nuevos. "
                        f"Total: {len(scraped_products)}"
                    )

                    # Si la página entera eran duplicados → llegamos al final real
                    if nuevos == 0:
                        self.logger.info(f"{categoria} p{page_num}: solo duplicados, fin de categoría.")
                        break

                    page_num += 1
                    await asyncio.sleep(random.uniform(self.DELAY_MIN, self.DELAY_MAX))

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
