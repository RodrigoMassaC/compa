"""
Spiders para Farmatodo Venezuela.
Implementa dos fases:
- FarmatodoIndexSpider: Parsea el sitemap XML para obtener todas las URLs de productos
- FarmatodoDetailSpider: Usa Playwright (con concurrencia) para extraer datos de cada producto
"""
import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from typing import List, Optional
from decimal import Decimal

import httpx
import redis.asyncio as aioredis
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.schemas.scraper_schema import ScrapedProduct
from app.services.scraper.base_spider import BaseSpider


class FarmatodoIndexSpider(BaseSpider):
    """
    Fase A: Parsea el sitemap de productos de Farmatodo para obtener todas las URLs.
    No requiere Playwright — es una sola request HTTP al XML del sitemap.
    Resultado: ~19,000 URLs cargadas en Redis en ~2 segundos.
    """

    SITEMAP_URL = "https://www.farmatodo.com.ve/sitemap-products.xml"
    REDIS_KEY = "farmatodo:product_queue"

    def __init__(self):
        super().__init__()

    async def run(self) -> List[ScrapedProduct]:
        """Descarga el sitemap XML y carga todas las URLs de productos en Redis."""
        self.logger.info("Fase A: descargando sitemap de productos...")
        r = aioredis.from_url(settings.redis_url, decode_responses=True)

        try:
            # Descargar sitemap XML
            headers = self._get_headers()
            # No pedir compresión para evitar problemas de decodificación
            headers.pop("Accept-Encoding", None)
            async with httpx.AsyncClient(
                headers=headers,
                timeout=60,
                follow_redirects=True
            ) as client:
                resp = await client.get(self.SITEMAP_URL)
                resp.raise_for_status()

            # Usar resp.content (bytes) y decodificar manualmente
            content = resp.content
            self.logger.info(f"Sitemap descargado: {len(content)} bytes")

            # Si viene comprimido con gzip, descomprimir
            import gzip
            if content[:2] == b'\x1f\x8b':
                content = gzip.decompress(content)
                self.logger.info(f"Sitemap descomprimido: {len(content)} bytes")

            xml_text = content.decode("utf-8")

            # Parsear XML
            root = ET.fromstring(xml_text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            count_total = 0
            count_new = 0

            for url_elem in root.findall(".//sm:url/sm:loc", ns):
                url = url_elem.text.strip() if url_elem.text else ""

                if "/producto/" not in url:
                    continue

                count_total += 1

                # Extraer SKU del slug: /producto/111004145-depilacion-cera-mila → "111004145"
                slug = url.rstrip("/").split("/")[-1]
                sku = slug.split("-")[0] if slug else "UNKNOWN"

                payload = json.dumps({"sku": str(sku), "url": url})
                was_added = await r.sadd(self.REDIS_KEY, payload)
                if was_added:
                    count_new += 1

            self.logger.info(
                f"Fase A completada: {count_total} URLs en sitemap, "
                f"{count_new} nuevas cargadas en Redis"
            )
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Error HTTP descargando sitemap: {e.response.status_code}")
        except ET.ParseError as e:
            self.logger.error(f"Error parseando XML del sitemap: {e}")
        except Exception as e:
            self.logger.error(f"Error en Fase A: {e}")
        finally:
            await r.aclose()

        return []


class FarmatodoDetailSpider(BaseSpider):
    """
    Fase B: Lee URLs de Redis y usa Playwright para extraer nombre y precios.
    Procesa múltiples productos en paralelo (CONCURRENCY páginas simultáneas).
    """

    REDIS_QUEUE = "farmatodo:product_queue"
    REDIS_PROCESSING = "farmatodo:processing"
    REDIS_DONE = "farmatodo:done"

    # Configuración de concurrencia
    CONCURRENCY = 4
    DELAY_MIN = 0.5
    DELAY_MAX = 1.5

    def __init__(self, max_products: Optional[int] = None):
        super().__init__()
        self.max_products = max_products
        self._count = 0
        self._count_lock = asyncio.Lock()

    async def run(self) -> List[ScrapedProduct]:
        self.logger.info(
            f"Fase B: extracción paralela con {self.CONCURRENCY} workers"
        )
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        sem = asyncio.Semaphore(self.CONCURRENCY)
        saved_count = 0

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self._get_random_ua(),
                    viewport={"width": 1280, "height": 800}
                )

                async def worker(payload_raw: str):
                    """Procesa un producto individual con semáforo de concurrencia."""
                    nonlocal saved_count
                    async with sem:
                        try:
                            payload = json.loads(payload_raw)
                            url = payload["url"]
                            sku = payload["sku"]

                            await r.sadd(self.REDIS_PROCESSING, payload_raw)

                            product = await self._process_product_url(context, url, sku)

                            if product:
                                await self._save_to_db(product)
                                async with self._count_lock:
                                    saved_count += 1
                                    if saved_count % 100 == 0:
                                        self.logger.info(
                                            f"📊 Progreso: {saved_count} productos guardados"
                                        )

                            await r.srem(self.REDIS_PROCESSING, payload_raw)
                            await r.sadd(self.REDIS_DONE, payload_raw)

                            await self._random_delay()
                        except Exception as e:
                            self.logger.error(f"Error en worker para {payload_raw[:80]}: {e}")
                            await r.srem(self.REDIS_PROCESSING, payload_raw)
                            await r.sadd(self.REDIS_DONE, payload_raw)

                # Procesar en batches para no crear miles de tasks en memoria
                BATCH_SIZE = self.CONCURRENCY * 10  # 40 tasks por batch

                while True:
                    tasks = []

                    for _ in range(BATCH_SIZE):
                        # Verificar límite
                        if self.max_products and saved_count >= self.max_products:
                            self.logger.info(
                                f"Alcanzado límite de {self.max_products} productos"
                            )
                            break

                        payload_raw = await r.spop(self.REDIS_QUEUE)
                        if not payload_raw:
                            break

                        tasks.append(asyncio.create_task(worker(payload_raw)))

                    if not tasks:
                        self.logger.info("Cola de productos vacía.")
                        break

                    # Esperar a que termine el batch
                    await asyncio.gather(*tasks, return_exceptions=True)

                    # Check si alcanzamos el límite
                    if self.max_products and saved_count >= self.max_products:
                        break

                await context.close()
                await browser.close()
        finally:
            await r.aclose()

        self.logger.info(f"Fase B finalizada. Productos guardados: {saved_count}")
        return []

    async def _process_product_url(self, context, url: str, sku: str) -> Optional[ScrapedProduct]:
        """Procesa una URL individual usando Playwright y retries."""
        max_retries = 3
        page = await context.new_page()

        for attempt in range(max_retries):
            self.logger.info(f"Leyendo URL (intento {attempt+1}/{max_retries}): {url}")

            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)

                # Detectar 404 y skip sin retry
                if response and response.status == 404:
                    self.logger.warning(f"⏭️ 404 para {url}, saltando")
                    await page.close()
                    return None

                # Esperar carga dinámica de Angular
                await page.wait_for_timeout(3000)

                content = await page.content()

                # Detectar página de error/404 por contenido
                if "no encontrado" in content.lower() or "página no existe" in content.lower():
                    self.logger.warning(f"⏭️ Producto no encontrado: {url}")
                    await page.close()
                    return None

                soup = BeautifulSoup(content, "lxml")

                h1_tag = soup.find("h1")
                nombre = h1_tag.get_text(strip=True) if h1_tag else None
                if not nombre:
                    title_tag = soup.find("title")
                    nombre = title_tag.get_text(strip=True).replace(" | Farmatodo", "") if title_tag else "Sin Nombre"

                precio_raw = None

                # Extraer precios del DOM con Playwright JS
                precio_raw = await page.evaluate('''() => {
                    const price_el = document.querySelector('div.product-purchase__price span')
                                  || document.querySelector('.product-purchase__price--active')
                                  || document.querySelector('.product-detail__mobile-price');
                    if (price_el) return price_el.innerText;

                    // Fallback: buscar elementos con "Bs."
                    const spans = Array.from(document.querySelectorAll('p, span, h2, h3'));
                    const bs_span = spans.find(el => el.innerText.includes('Bs.') && /\\d/.test(el.innerText));
                    return bs_span ? bs_span.innerText : null;
                }''')

                if not nombre or not precio_raw:
                    self.logger.warning(f"Faltan datos para {url}. Nombre: {nombre}, Precio: {precio_raw}")
                    raise ValueError("HTML no contiene datos o estructura cambió")

                # Parsear precio VES
                precio_decimal = self._parse_precio_ves(precio_raw)

                producto = ScrapedProduct(
                    nombre_original=nombre,
                    precio_bruto=precio_decimal,
                    moneda_origen="VES",
                    sku_comercio=sku,
                    url_origen=url
                )

                self.logger.info(f"✅ Extraído: {nombre} -> {precio_decimal}")
                await page.close()
                return producto

            except Exception as e:
                self.logger.warning(f"Error procesando {url}: {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"❌ Fallo permanente para {url}")
                await page.wait_for_timeout(3000)

        await page.close()
        return None

    @staticmethod
    def _parse_precio_ves(precio_raw: str) -> Decimal:
        """Parsea un precio en formato VES a Decimal."""
        import re as _re

        precio_limpio = precio_raw.replace("Bs.", "").replace("Bs", "").strip()
        precio_limpio = _re.sub(r'\s+', '', precio_limpio)

        try:
            tiene_coma = "," in precio_limpio
            tiene_punto = "." in precio_limpio

            if tiene_coma and tiene_punto:
                if precio_limpio.rfind(",") > precio_limpio.rfind("."):
                    # Formato VE: 1.312,10 (punto=miles, coma=decimal)
                    precio_limpio = precio_limpio.replace(".", "").replace(",", ".")
                else:
                    # Formato US: 1,312.10 (coma=miles, punto=decimal)
                    precio_limpio = precio_limpio.replace(",", "")
            elif tiene_coma:
                partes = precio_limpio.split(",")
                if len(partes) == 2 and len(partes[1]) <= 2:
                    precio_limpio = precio_limpio.replace(",", ".")
                else:
                    precio_limpio = precio_limpio.replace(",", "")
            elif tiene_punto:
                puntos = precio_limpio.split(".")
                if len(puntos) > 2:
                    if len(puntos[-1]) == 2:
                        entero = "".join(puntos[:-1])
                        precio_limpio = f"{entero}.{puntos[-1]}"
                    else:
                        precio_limpio = precio_limpio.replace(".", "")
                elif len(puntos) == 2 and len(puntos[1]) == 3:
                    precio_limpio = precio_limpio.replace(".", "")

            return Decimal(precio_limpio)
        except Exception:
            return Decimal("0.0")

    async def _save_to_db(self, product: ScrapedProduct):
        """Guarda el producto en la base de datos de PostgreSQL."""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import text

                q_est = text("SELECT id_establecimiento FROM establecimientos e JOIN cadenas_comerciales c ON c.id_cadena = e.id_cadena WHERE c.nombre_cadena = 'Farmatodo' LIMIT 1")
                result = await session.execute(q_est)
                row = result.fetchone()

                id_est = row[0] if row else None

                if id_est:
                    query2 = text("""
                        INSERT INTO productos_crudos (
                            id_establecimiento, nombre_original, sku_comercio, url_origen, estado_mapeo
                        ) VALUES (
                            :id_est, :nombre, :sku, :url, 'PENDIENTE'
                        ) ON CONFLICT (id_establecimiento, sku_comercio)
                        DO UPDATE SET
                            nombre_original = EXCLUDED.nombre_original,
                            url_origen = EXCLUDED.url_origen
                    """)

                    await session.execute(query2, {
                        "id_est": id_est,
                        "nombre": product.nombre_original,
                        "sku": product.sku_comercio,
                        "url": product.url_origen
                    })
                    await session.commit()
                else:
                    self.logger.error("No se encontró establecimiento Farmatodo en DB.")

        except Exception as e:
            self.logger.error(f"Error guardando en DB: {e}")
