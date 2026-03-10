"""
Spiders para Locatel Venezuela.
Plataforma: VTEX
Moneda: VES (Bolívares Soberanos, formato "Bs.S 2.456,03")

Paginación confirmada: ?page=N (10 productos/página)
Total catálogo: ~4000+ productos en Farmacia sola

Estrategia:
  Fase A (LocatelIndexSpider): recorre categorías con paginación ?page=N
  Fase B (LocatelDetailSpider): visita cada URL de producto para precio exacto
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

# ID del establecimiento Locatel en la DB
LOCATEL_ID_ESTABLECIMIENTO = "e2d24690-b4eb-434d-a191-b79d486ec75b"

BASE_URL = "https://www.locatel.com.ve"

# Categorías principales con sus slugs de URL.
# Cada una tiene paginación ?page=N, 10 productos por página.
CATEGORIAS = [
    "farmacia",
    "cuidado-personal",
    "cuidado-del-bebe",
    "nutricion-especializada",
    "dermocosmeticos",
    "alimentos",
    "hogar",
    "equipos-medicos",
]


class LocatelIndexSpider(BaseSpider):
    """
    Fase A: Recorre todas las categorías con paginación ?page=N usando Playwright.
    Extrae URLs y CODs (SKUs) de productos y los pone en Redis.
    """

    REDIS_KEY = "locatel:product_queue"

    def __init__(self):
        super().__init__()

    async def run(self) -> List[ScrapedProduct]:
        self.logger.info("Iniciando LocatelIndexSpider (Fase A)")
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

                for categoria in CATEGORIAS:
                    await self._scrape_categoria(context, r, categoria)

                await context.close()
                await browser.close()
        finally:
            total = await r.scard(self.REDIS_KEY)
            self.logger.info(f"Fase A finalizada. Total productos únicos en Redis: {total}")
            await r.aclose()

        return []

    async def _scrape_categoria(self, context, redis_client: aioredis.Redis, categoria: str):
        """Recorre todas las páginas de una categoría."""
        self.logger.info(f"Procesando categoría: {categoria}")
        page_num = 1
        total_nuevos = 0

        while True:
            url = f"{BASE_URL}/{categoria}?page={page_num}"
            nuevos, hay_mas = await self._process_page(context, redis_client, url, page_num)
            total_nuevos += nuevos

            if not hay_mas:
                self.logger.info(f"  [{categoria}] Fin en página {page_num}. Total nuevos: {total_nuevos}")
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

            cards = soup.select('[class*="galleryItem"]')
            if not cards:
                return 0, False

            self.logger.info(f"  Página {page_num}: {len(cards)} productos")

            for card in cards:
                link_tag = card.select_one('a[href*="/p"]')
                if not link_tag:
                    continue

                href = link_tag.get("href", "")
                full_url = f"{BASE_URL}{href}" if href.startswith("/") else href

                # SKU: texto "COD: XXXXXXX"
                cod_text = None
                for el in card.find_all(string=re.compile(r"COD:\s*\d+")):
                    cod_text = el.strip()
                    break

                sku = re.sub(r"COD:\s*", "", cod_text).strip() if cod_text else \
                      href.rstrip("/p").split("/")[-1]

                payload = json.dumps({"sku": sku, "url": full_url})
                was_added = await redis_client.sadd(self.REDIS_KEY, payload)
                if was_added:
                    nuevos += 1

            # Hay más si encontramos 10 productos (tamaño de página confirmado)
            hay_mas = len(cards) >= 8

        except Exception as e:
            self.logger.error(f"Error en {url}: {e}")
        finally:
            await page.close()

        return nuevos, hay_mas


class LocatelDetailSpider(BaseSpider):
    """
    Fase B: Lee URLs de Redis, visita cada página de producto con Playwright
    y extrae nombre + precio. Guarda en productos_crudos + historial_precios.
    """

    REDIS_QUEUE = "locatel:product_queue"
    REDIS_PROCESSING = "locatel:processing"
    REDIS_DONE = "locatel:done"

    def __init__(self, max_products: Optional[int] = None):
        super().__init__()
        self.max_products = max_products

    async def run(self) -> List[ScrapedProduct]:
        self.logger.info("Iniciando LocatelDetailSpider (Fase B)")
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

                # Nombre
                nombre = None
                h1 = soup.find("h1")
                if h1:
                    nombre = h1.get_text(strip=True)
                if not nombre:
                    name_el = soup.select_one('[class*="productName"], [class*="productBrand"]')
                    if name_el:
                        nombre = name_el.get_text(strip=True)
                if not nombre:
                    title = soup.find("title")
                    if title:
                        nombre = title.get_text(strip=True).replace(" - Locatel Venezuela", "").strip()

                # Precio
                precio_raw = await page.evaluate("""() => {
                    const el = document.querySelector('[class*="sellingPrice"]')
                           || document.querySelector('[class*="price"]');
                    return el ? el.innerText.trim() : null;
                }""")

                if not nombre or not precio_raw:
                    raise ValueError(f"Datos incompletos: nombre={nombre}, precio={precio_raw}")

                precio_decimal = self._parse_precio_ves(precio_raw)

                producto = ScrapedProduct(
                    nombre_original=nombre,
                    precio_bruto=precio_decimal,
                    moneda_origen="VES",
                    sku_comercio=sku,
                    url_origen=url,
                )

                self.logger.info(f"✅ {nombre[:60]} → {precio_decimal} VES")
                await page.close()
                return producto

            except Exception as e:
                self.logger.warning(f"Error en {url} (intento {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await page.wait_for_timeout(3000)

        await page.close()
        self.logger.error(f"❌ Fallo permanente: {url}")
        return None

    def _parse_precio_ves(self, precio_raw: str) -> Decimal:
        """
        Parsea precios venezolanos en formato VTEX/Locatel.
        "Bs.S 2.456,03" → 2456.03
        "Bs. 1.800,31"  → 1800.31
        """
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
            self.logger.warning(f"No se pudo parsear precio '{precio_raw}', usando 0.0")
            return Decimal("0.0")

    async def _save_to_db(self, product: ScrapedProduct):
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
                    "id_est": LOCATEL_ID_ESTABLECIMIENTO,
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
                        id_producto_crudo, precio_bruto, moneda_origen, fuente_datos, fecha_lectura
                    ) VALUES (
                        :id_prod, :precio, 'VES', 'SCRAPING_WEB', NOW()
                    )
                """)

                await session.execute(q_precio, {
                    "id_prod": id_producto_crudo,
                    "precio":  float(product.precio_bruto),
                })

                await session.commit()

        except Exception as e:
            self.logger.error(f"Error guardando en DB ({product.nombre_original[:40]}): {e}")
