"""
Spider para Farmago Venezuela — Fase A (índice).
Recorre la tienda Odoo eCommerce de farmago.com.ve paginando ?page=N
y extrae nombre, SKU y URL de cada producto, insertándolos en productos_crudos.

Los precios se extraen en la Fase B por farmago_prices.FarmagoPriceSpider,
igual que el patrón usado por farmatodo / farmatodo_prices.

Usa Playwright para renderizar el JavaScript de Odoo antes de parsear.
"""
import asyncio
import random
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.core.database import AsyncSessionLocal
from app.schemas.scraper_schema import ScrapedProduct
from app.services.scraper.base_spider import BaseSpider


BASE_URL = "https://www.farmago.com.ve"
SHOP_URL = f"{BASE_URL}/shop"


class FarmagoSpider(BaseSpider):
    """
    Spider de una sola fase para Farmago Venezuela.

    Itera sobre las páginas de la tienda (?page=N) hasta que no haya
    más productos, extrae los campos disponibles desde el HTML renderizado
    por Odoo eCommerce e inserta cada producto en productos_crudos.
    """

    # Override del rango de delay definido en BaseSpider
    DELAY_MIN: float = 2.0
    DELAY_MAX: float = 3.5

    def __init__(self, max_pages: Optional[int] = None) -> None:
        super().__init__()
        self.max_pages = max_pages

    # ------------------------------------------------------------------
    # Método principal
    # ------------------------------------------------------------------

    async def run(self) -> List[ScrapedProduct]:
        self.logger.info("Iniciando FarmagoSpider — scraping de farmago.com.ve")
        scraped_products: List[ScrapedProduct] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self._get_random_ua(),
                viewport={"width": 1280, "height": 800},
            )

            page_num = 1
            while True:
                if self.max_pages and page_num > self.max_pages:
                    self.logger.info(
                        f"Límite de páginas alcanzado: {self.max_pages}"
                    )
                    break

                products = await self._scrape_page(context, page_num)

                if not products:
                    self.logger.info(
                        f"No se encontraron productos en página {page_num}. "
                        "Finalizando paginación."
                    )
                    break

                for product in products:
                    scraped_products.append(product)
                    await self._save_to_db(product)

                self.logger.info(
                    f"Página {page_num}: {len(products)} productos extraídos. "
                    f"Total acumulado: {len(scraped_products)}"
                )

                page_num += 1

                # Delay aleatorio entre páginas para no sobrecargar el servidor
                delay = random.uniform(self.DELAY_MIN, self.DELAY_MAX)
                self.logger.debug(f"Esperando {delay:.2f}s antes de la siguiente página...")
                await asyncio.sleep(delay)

            await context.close()
            await browser.close()

        self.logger.info(
            f"FarmagoSpider finalizado. Total productos guardados: {len(scraped_products)}"
        )
        return scraped_products

    # ------------------------------------------------------------------
    # Scraping de una página
    # ------------------------------------------------------------------

    async def _scrape_page(
        self, context, page_num: int
    ) -> List[ScrapedProduct]:
        """Navega a la página N de la tienda y extrae todos los productos."""
        url = f"{SHOP_URL}?page={page_num}"
        self.logger.info(f"Navegando a: {url}")

        page = await context.new_page()
        products: List[ScrapedProduct] = []

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            # Esperar renderizado de Odoo (JS pesado)
            await page.wait_for_timeout(4000)
            # Scroll suave para disparar lazy-load de imágenes
            await page.mouse.wheel(0, 800)
            await page.wait_for_timeout(1000)

            content = await page.content()
            soup = BeautifulSoup(content, "lxml")

            # Cada producto está dentro de un div.product_price o similar;
            # el anchor con clase oe_product_image_link agrupa imagen + datos.
            product_blocks = soup.select(".oe_product")
            if not product_blocks:
                # Fallback: intentar con el contenedor alternativo de Odoo 16/17
                product_blocks = soup.select("[itemtype='http://schema.org/Product']")

            if not product_blocks:
                self.logger.warning(
                    f"No se encontraron bloques de producto en página {page_num}. "
                    "El sitio puede haber cambiado su estructura."
                )
                return products

            for block in product_blocks:
                product = self._parse_product_block(block)
                if product:
                    products.append(product)

        except Exception as e:
            self.logger.error(f"Error navegando/parseando página {page_num}: {e}")
        finally:
            await page.close()

        return products

    # ------------------------------------------------------------------
    # Parsing de un bloque de producto
    # ------------------------------------------------------------------

    def _parse_product_block(self, block) -> Optional[ScrapedProduct]:
        """Extrae nombre, url y SKU de un bloque <div.oe_product>."""
        try:
            # --- Nombre ---
            nombre_tag = block.select_one('[itemprop="name"].text-primary')
            if not nombre_tag:
                nombre_tag = block.select_one('[itemprop="name"]')
            nombre = nombre_tag.get_text(strip=True) if nombre_tag else None

            if not nombre:
                self.logger.debug("Bloque sin nombre, se omite.")
                return None

            # --- URL del producto ---
            link_tag = block.select_one(".oe_product_image_link")
            if not link_tag:
                link_tag = block.select_one("a[href]")

            url_producto = None
            if link_tag:
                href = link_tag.get("href", "")
                if href:
                    url_producto = (
                        href if href.startswith("http") else f"{BASE_URL}{href}"
                    )

            # SKU: usar la ruta relativa del producto como identificador único
            sku = url_producto.replace(BASE_URL, "").strip("/") if url_producto else nombre

            # precio_bruto / moneda_origen NO se guardan aquí:
            # los extrae farmago_prices.FarmagoPriceSpider en la Fase B.
            product = ScrapedProduct(
                nombre_original=nombre,
                precio_bruto=Decimal("0.01"),   # placeholder, no se persiste
                moneda_origen="VES",          # placeholder, no se persiste
                sku_comercio=sku,
                url_origen=url_producto or SHOP_URL,
            )

            self.logger.debug(f"✅ Parseado: {nombre}  ({sku})")
            return product

        except Exception as e:
            self.logger.warning(f"Error parseando bloque de producto: {e}")
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_precio(self, raw: Optional[str]) -> Decimal:
        """
        Convierte un string de precio en Decimal.
        Soporta formatos: '15000', '15.000,50', '15,000.50', '15000.50'
        """
        if not raw:
            return Decimal("0.0")

        import re
        # Quitar símbolo de moneda y espacios
        limpio = re.sub(r"[^\d,.]", "", raw.strip())

        if not limpio:
            return Decimal("0.0")

        try:
            tiene_coma = "," in limpio
            tiene_punto = "." in limpio

            if tiene_coma and tiene_punto:
                # Si la coma aparece después del último punto → VE (punto=miles, coma=decimal)
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
                partes = limpio.split(".")
                if len(partes) > 2:
                    # Múltiples puntos: 15.000.50 → 15000.50
                    if len(partes[-1]) == 2:
                        entero = "".join(partes[:-1])
                        limpio = f"{entero}.{partes[-1]}"
                    else:
                        limpio = limpio.replace(".", "")
                elif len(partes) == 2 and len(partes[1]) == 3:
                    # 15.000 → solo miles
                    limpio = limpio.replace(".", "")
                # else: 150.50 → decimal normal

            return Decimal(limpio)

        except (InvalidOperation, ValueError):
            self.logger.warning(f"No se pudo parsear precio desde '{raw}'. Devuelve 0.0")
            return Decimal("0.0")

    async def _save_to_db(self, product: ScrapedProduct) -> None:
        """Inserta el producto en productos_crudos vía AsyncSession."""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import text

                # Obtener el id_establecimiento de Farmago
                q_est = text(
                    """
                    SELECT e.id_establecimiento
                    FROM establecimientos e
                    JOIN cadenas_comerciales c ON c.id_cadena = e.id_cadena
                    WHERE c.nombre_cadena = 'Farmago'
                    LIMIT 1
                    """
                )
                result = await session.execute(q_est)
                row = result.fetchone()
                id_est = row[0] if row else None

                if not id_est:
                    self.logger.error(
                        "No se encontró ningún establecimiento 'Farmago' en la DB. "
                        "Asegúrate de que la cadena comercial esté registrada."
                    )
                    return

                # Solo insertar los campos que existen en productos_crudos.
                # precio_bruto / moneda_origen van en historial_precios (Fase B).
                q_insert = text(
                    """
                    INSERT INTO productos_crudos (
                        id_establecimiento,
                        nombre_original,
                        sku_comercio,
                        url_origen,
                        estado_mapeo
                    ) VALUES (
                        :id_est,
                        :nombre,
                        :sku,
                        :url,
                        'PENDIENTE'
                    )
                    ON CONFLICT (id_establecimiento, sku_comercio)
                    DO UPDATE SET
                        nombre_original = EXCLUDED.nombre_original,
                        url_origen      = EXCLUDED.url_origen
                    """
                )

                await session.execute(
                    q_insert,
                    {
                        "id_est": id_est,
                        "nombre": product.nombre_original,
                        "sku": product.sku_comercio,
                        "url": product.url_origen,
                    },
                )
                await session.commit()
                self.logger.debug(
                    f"💾 Guardado en DB: {product.nombre_original}"
                )

        except Exception as e:
            self.logger.error(f"Error guardando '{product.nombre_original}' en DB: {e}")
