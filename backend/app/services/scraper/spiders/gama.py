"""
Spiders para Excelsior Gama Venezuela (gamaenlinea.com).
Plataforma: SAP Commerce / Hybris
Moneda: USD (precios en "Ref.", donde Ref. = USD según tasa BCV)

Selectores confirmados:
  - Nombre: a.cx-product-name
  - Precio: cx-product-price → "Total Ref. 3,75"
  - SKU: extraído de URL /p/{SKU}
  - Paginación: ?currentPage=N (base-0), 12 productos/página

Estrategia:
  Fase A (GamaIndexSpider): recorre categorías con paginación ?currentPage=N
  Fase B (GamaDetailSpider): visita cada URL de producto para precio exacto
"""
import asyncio
import json
import logging
import re
from typing import List, Optional
from decimal import Decimal

import redis.asyncio as aioredis
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.schemas.scraper_schema import ScrapedProduct
from app.services.scraper.base_spider import BaseSpider

# ID del establecimiento Gama en la DB
GAMA_ID_ESTABLECIMIENTO = "3411bdba-501d-4d0f-8cb5-d598314502e4"

BASE_URL = "https://gamaenlinea.com"

# Categorías principales de Gama (slugs confirmados del menú)
CATEGORIAS = [
    # Despensa
    ("azucares-endulzantes", "A0104"),
    ("cafe", "A0107"),
    ("aceites-vinagres", "A0109"),
    ("cereales", "A0115"),
    ("lacteos", "A0101"),
    ("harinas-pastas", "A0102"),
    ("arroz-granos", "A0103"),
    ("dulces-galletas-reposteria", "A0106"),
    ("panaderia", "A0111"),
    # Condimentos y conservas
    ("condimentos-salsas", "A0116"),
    ("enlatados-conservas", "A0117"),
    ("sopas-cremas", "A0121"),
    ("snacks-golosinas", "A0120"),
    # Bebidas
    ("agua", "B0101"),
    ("bebidas-gaseosas", "B0102"),
    ("jugos-nectares", "B0103"),
    # Cuidado personal
    ("cuidado-capilar", "E0101"),
    ("cuidado-corporal", "E0102"),
    ("cuidado-facial", "E0103"),
    ("higiene-oral", "E0104"),
    ("desodorantes", "E0105"),
    ("farmacia", "E0106"),
    # Hogar
    ("limpieza-hogar", "F0101"),
    ("detergentes", "F0102"),
    ("insecticidas", "F0103"),
    # Otros
    ("licores", "G0101"),
    ("hogar", "H0101"),
    ("mascotas", "I0101"),
]


class GamaIndexSpider(BaseSpider):
    """
    Fase A: Recorre todas las categorías con paginación ?currentPage=N usando Playwright.
    Extrae URLs y SKUs de productos → los pone en Redis.
    """

    REDIS_KEY = "gama:product_queue"

    def __init__(self):
        super().__init__()

    async def run(self) -> List[ScrapedProduct]:
        self.logger.info("Iniciando GamaIndexSpider (Fase A)")
        r = aioredis.from_url(settings.redis_url, decode_responses=True)

        try:
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

                for slug, codigo in CATEGORIAS:
                    await self._scrape_categoria(context, r, slug, codigo)

                await context.close()
                await browser.close()
        finally:
            total = await r.scard(self.REDIS_KEY)
            self.logger.info(f"Fase A finalizada. Total productos únicos en Redis: {total}")
            await r.aclose()

        return []

    async def _scrape_categoria(self, context, redis_client: aioredis.Redis, slug: str, codigo: str):
        """Recorre todas las páginas de una categoría."""
        self.logger.info(f"Procesando categoría: {slug} ({codigo})")
        page_num = 0  # SAP Hybris usa base-0
        total_nuevos = 0

        while True:
            if page_num == 0:
                url = f"{BASE_URL}/es/{slug}/c/{codigo}"
            else:
                url = f"{BASE_URL}/es/{slug}/c/{codigo}?currentPage={page_num}"

            nuevos, hay_mas = await self._process_page(context, redis_client, url, page_num)
            total_nuevos += nuevos

            if not hay_mas:
                self.logger.info(f"  [{slug}] Fin en página {page_num + 1}. Total nuevos: {total_nuevos}")
                break

            page_num += 1
            await asyncio.sleep(0.5)

    async def _process_page(self, context, redis_client: aioredis.Redis, url: str, page_num: int):
        """
        Procesa una página de categoría.
        Retorna (nuevos_agregados: int, hay_mas_paginas: bool)
        """
        page = await context.new_page()
        nuevos = 0
        hay_mas = False

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4000)

            content = await page.content()
            soup = BeautifulSoup(content, "lxml")

            # Productos: links con href que termina en /p/{SKU}
            product_links = soup.select('a.cx-product-name[href*="/p/"]')

            # Fallback: cualquier link /p/
            if not product_links:
                product_links = soup.select('a[href*="/p/"]')
                # Deduplicar por href
                seen = set()
                unique_links = []
                for l in product_links:
                    href = l.get("href", "")
                    if href not in seen and "/p/" in href:
                        seen.add(href)
                        unique_links.append(l)
                product_links = unique_links

            if not product_links:
                return 0, False

            self.logger.info(f"  Página {page_num + 1}: {len(product_links)} productos")

            for link in product_links:
                href = link.get("href", "")
                full_url = f"{BASE_URL}{href}" if href.startswith("/") else href

                # SKU: último segmento después de /p/
                sku = href.split("/p/")[-1].strip("/") if "/p/" in href else href.split("/")[-1]

                payload = json.dumps({"sku": sku, "url": full_url})
                was_added = await redis_client.sadd(self.REDIS_KEY, payload)
                if was_added:
                    nuevos += 1

            # Hay más páginas si encontramos 12 productos (tamaño de página confirmado)
            hay_mas = len(product_links) >= 12

        except Exception as e:
            self.logger.error(f"Error en {url}: {e}")
        finally:
            await page.close()

        return nuevos, hay_mas


class GamaDetailSpider(BaseSpider):
    """
    Fase B: Lee URLs de Redis, visita cada página de producto con Playwright
    y extrae nombre + precio. Guarda en productos_crudos + historial_precios.
    """

    REDIS_QUEUE = "gama:product_queue"
    REDIS_PROCESSING = "gama:processing"
    REDIS_DONE = "gama:done"

    def __init__(self, max_products: Optional[int] = None):
        super().__init__()
        self.max_products = max_products

    async def run(self) -> List[ScrapedProduct]:
        self.logger.info("Iniciando GamaDetailSpider (Fase B)")
        scraped_products: List[ScrapedProduct] = []
        r = aioredis.from_url(settings.redis_url, decode_responses=True)

        try:
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

                count = 0
                while True:
                    if self.max_products and count >= self.max_products:
                        self.logger.info(f"Límite de prueba alcanzado: {self.max_products}")
                        break

                    payload_raw = await r.spop(self.REDIS_QUEUE)
                    if not payload_raw:
                        self.logger.info("Cola vacía — Fase B completada.")
                        break

                    await r.sadd(self.REDIS_PROCESSING, payload_raw)
                    payload = json.loads(payload_raw)
                    url = payload["url"]
                    sku = payload["sku"]

                    product = await self._process_product_url(context, url, sku)

                    if product:
                        scraped_products.append(product)
                        await self._save_to_db(product)
                        count += 1

                    await r.srem(self.REDIS_PROCESSING, payload_raw)
                    await r.sadd(self.REDIS_DONE, payload_raw)

                await context.close()
                await browser.close()
        finally:
            await r.aclose()

        self.logger.info(f"Fase B finalizada. Productos guardados: {len(scraped_products)}")
        return scraped_products

    async def _process_product_url(self, context, url: str, sku: str) -> Optional[ScrapedProduct]:
        max_retries = 3
        page = await context.new_page()

        for attempt in range(max_retries):
            self.logger.info(f"Procesando (intento {attempt + 1}/{max_retries}): {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(3500)

                content = await page.content()
                soup = BeautifulSoup(content, "lxml")

                # Nombre del producto
                nombre = None
                # SAP CX: h1 en página de detalle
                h1 = soup.find("h1")
                if h1:
                    nombre = h1.get_text(strip=True)
                if not nombre:
                    name_el = soup.select_one("cx-product-intro .name, a.cx-product-name, [class*='productName']")
                    if name_el:
                        nombre = name_el.get_text(strip=True)
                if not nombre:
                    title = soup.find("title")
                    if title:
                        nombre = title.get_text(strip=True).replace(" | Gama en Línea", "").strip()

                # Precio en Ref. (USD)
                precio_raw = await page.evaluate("""() => {
                    const el = document.querySelector('[class*="price"]') ||
                               document.querySelector('.price') ||
                               document.querySelector('cx-product-price');
                    return el ? el.innerText.trim() : null;
                }""")

                if not nombre or not precio_raw:
                    raise ValueError(f"Datos incompletos: nombre={nombre}, precio={precio_raw}")

                precio_decimal = self._parse_precio_usd(precio_raw)

                producto = ScrapedProduct(
                    nombre_original=nombre,
                    precio_bruto=precio_decimal,
                    moneda_origen="USD",
                    sku_comercio=sku,
                    url_origen=url,
                )

                self.logger.info(f"✅ {nombre[:60]} → {precio_decimal} USD")
                await page.close()
                return producto

            except Exception as e:
                self.logger.warning(f"Error en {url} (intento {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await page.wait_for_timeout(3000)

        await page.close()
        self.logger.error(f"❌ Fallo permanente: {url}")
        return None

    def _parse_precio_usd(self, precio_raw: str) -> Decimal:
        """
        Parsea precios en formato Gama/SAP Hybris.
        Ejemplos: "Total Ref. 3,75" → 3.75
                  "Ref. 12,50"      → 12.50
                  "Total Ref. 3.75" → 3.75
        """
        try:
            # Quitar "Total", "Ref.", espacios
            limpio = re.sub(r"Total|Ref\.|Ref|[\s]", "", precio_raw, flags=re.IGNORECASE).strip()

            # Gama usa coma como decimal: "3,75" → "3.75"
            if "," in limpio and "." not in limpio:
                limpio = limpio.replace(",", ".")
            elif "," in limpio and "." in limpio:
                # "1.234,56" → miles con punto, decimal con coma
                limpio = limpio.replace(".", "").replace(",", ".")

            return Decimal(limpio)
        except Exception:
            self.logger.warning(f"No se pudo parsear precio '{precio_raw}', usando 0.0")
            return Decimal("0.0")

    async def _save_to_db(self, product: ScrapedProduct):
        """Inserta en productos_crudos y registra precio en historial_precios."""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import text

                q_upsert = text("""
                    INSERT INTO productos_crudos (
                        id_establecimiento, nombre_original, sku_comercio,
                        url_origen, estado_mapeo
                    ) VALUES (
                        :id_est, :nombre, :sku, :url, 'PENDIENTE'
                    )
                    ON CONFLICT (id_establecimiento, sku_comercio)
                    DO UPDATE SET
                        nombre_original = EXCLUDED.nombre_original,
                        url_origen      = EXCLUDED.url_origen
                    RETURNING id_producto_crudo
                """)

                result = await session.execute(q_upsert, {
                    "id_est": GAMA_ID_ESTABLECIMIENTO,
                    "nombre": product.nombre_original,
                    "sku":    product.sku_comercio,
                    "url":    product.url_origen,
                })
                row = result.fetchone()
                if not row:
                    await session.commit()
                    return

                id_producto_crudo = row[0]

                q_precio = text("""
                    INSERT INTO historial_precios (
                        id_producto_crudo, precio_bruto, moneda_origen,
                        fuente_datos, fecha_lectura
                    ) VALUES (
                        :id_prod, :precio, 'USD', 'SCRAPING_WEB', NOW()
                    )
                """)

                await session.execute(q_precio, {
                    "id_prod": id_producto_crudo,
                    "precio":  float(product.precio_bruto),
                })

                await session.commit()

        except Exception as e:
            self.logger.error(f"Error guardando en DB ({product.nombre_original[:40]}): {e}")
