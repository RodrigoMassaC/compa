"""
Spiders para Farmatodo Venezuela.
Implementa dos fases:
- FarmatodoIndexSpider: Llama a la API de Algolia para obtener IDs y URLs de productos
- FarmatodoDetailSpider: Usa Playwright para extraer los datos crudos desde la página de detalle
"""
import asyncio
import json
import logging
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
# from app.models.prices import ProductosCrudos  # Asumiendo que existe el modelo


class FarmatodoIndexSpider(BaseSpider):
    """
    Fase A: Recorre las categorías usando Playwright para obtener el HTML renderizado.
    Extrae los SKUs y URLs para guardarlos en Redis.
    Como Playwright consume memoria, extraemos sólo las categorías vitales.
    """
    
    # URLs de sub-categorías (hojas del árbol) a scrapear — extraídas del sitemap oficial
    CATEGORIAS_URLS = [
        # Alimentos y Bebidas
        "https://www.farmatodo.com.ve/categorias/alimentos-y-bebidas/alimentos/alimentos-basicos",
        "https://www.farmatodo.com.ve/categorias/alimentos-y-bebidas/alimentos/cafe-te-infusiones",
        "https://www.farmatodo.com.ve/categorias/alimentos-y-bebidas/alimentos/cereales",
        "https://www.farmatodo.com.ve/categorias/alimentos-y-bebidas/bebidas/gaseosas",
        "https://www.farmatodo.com.ve/categorias/alimentos-y-bebidas/bebidas/lacteos",
        "https://www.farmatodo.com.ve/categorias/alimentos-y-bebidas/dulces-y-snacks/chocolates-tortas-galletas",
        "https://www.farmatodo.com.ve/categorias/alimentos-y-bebidas/dulces-y-snacks/snacks",
        # Bebé
        "https://www.farmatodo.com.ve/categorias/bebe/bebe-alimentos/formulas-y-leches-infantiles",
        "https://www.farmatodo.com.ve/categorias/bebe/higiene-del-bebe/panales",
        # Cuidado Personal
        "https://www.farmatodo.com.ve/categorias/cuidado-personal/cuidado-bucal/cremas-dentales",
        "https://www.farmatodo.com.ve/categorias/cuidado-personal/higiene-personal/desodorantes",
        "https://www.farmatodo.com.ve/categorias/cuidado-personal/higiene-personal/jabones",
        "https://www.farmatodo.com.ve/categorias/cuidado-personal/cuidado-del-cabello/champu",
        # Salud y Medicamentos
        "https://www.farmatodo.com.ve/categorias/salud-y-medicamentos/dolor-general/analgesico-y-antipiretico",
        "https://www.farmatodo.com.ve/categorias/salud-y-medicamentos/vitaminas-y-productos-naturales/multivitaminicos-",
        "https://www.farmatodo.com.ve/categorias/salud-y-medicamentos/vitaminas-y-productos-naturales/vitamina-c-",
        "https://www.farmatodo.com.ve/categorias/salud-y-medicamentos/salud-digestiva/antiacidos",
        "https://www.farmatodo.com.ve/categorias/salud-y-medicamentos/dermatologicos/antimicotico",
        "https://www.farmatodo.com.ve/categorias/salud-y-medicamentos/medicamentos/medicamentos",
        "https://www.farmatodo.com.ve/categorias/salud-y-medicamentos/salud-respiratoria-y-gripe/antigripales",
    ]
    
    REDIS_KEY = "farmatodo:product_queue"

    def __init__(self):
        super().__init__()

    async def run(self) -> List[ScrapedProduct]:
        """Extrae URLs de productos recorriendo categorías y las pone en Redis usando Playwright."""
        self.logger.info("Iniciando FarmatodoIndexSpider (Fase A) - Scraping con Playwright")
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                for cat_url in self.CATEGORIAS_URLS:
                    await self._process_category_playwright(browser, r, cat_url)
                await browser.close()
        finally:
            await r.aclose()
            
        return []

    async def _process_category_playwright(self, browser, redis_client: aioredis.Redis, url: str):
        self.logger.info(f"Procesando categoría URL: {url}")
        total_found = 0
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        try:
            # Esperar a que cargue la estructura básica y luego un tiempo prudente
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)  # Delay adicional para renderizado Angular SRR
            await page.wait_for_timeout(3000)  # Delay adicional para JS pesado
            
            # Hacer algo de scroll
            await page.mouse.wheel(0, 1000)
            await page.wait_for_timeout(1000)
            
            # Obtener el HTML renderizado
            content = await page.content()
            soup = BeautifulSoup(content, "lxml")
            
            # Buscar todos los links de producto
            product_links = soup.select("a.product-card__info-link")
            if not product_links:
                product_links = soup.select("a[href*='/producto/']")
                
            nuevos = 0
            for link in product_links:
                href = link.get("href")
                if href and "/producto/" in href:
                    parts = href.split("/")[-1].split("-")
                    sku = parts[0] if parts else "UNKNOWN"
                    
                    full_url = f"https://www.farmatodo.com.ve{href}" if href.startswith("/") else href
                    payload = json.dumps({"sku": str(sku), "url": full_url})
                    
                    was_added = await redis_client.sadd(self.REDIS_KEY, payload)
                    if was_added:
                        total_found += 1
                        nuevos += 1
                        
            self.logger.info(f"Categoría {url} finalizada. Total SKUs extraídos en Playwright: {total_found}")
            
        except Exception as e:
            self.logger.error(f"Error procesando categoría {url}: {e}")
        finally:
            await context.close()


class FarmatodoDetailSpider(BaseSpider):
    """
    Fase B: Lee URLs de Redis y usa Playwright para extraer nombre y precios de la página de detalle.
    Luego lo inserta en la base de datos PostgreSQL.
    """
    
    REDIS_QUEUE = "farmatodo:product_queue"
    REDIS_PROCESSING = "farmatodo:processing"
    REDIS_DONE = "farmatodo:done"

    def __init__(self, max_products: Optional[int] = None):
        super().__init__()
        self.max_products = max_products

    async def run(self) -> List[ScrapedProduct]:
        self.logger.info("Iniciando FarmatodoDetailSpider (Fase B) - Extracción con Playwright")
        scraped_products: List[ScrapedProduct] = []
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                
                count = 0
                while True:
                    if self.max_products and count >= self.max_products:
                        self.logger.info(f"Alcanzado el límite máximo de {self.max_products} productos de prueba.")
                        break
                        
                    # Mover de la cola principal a "processing" 
                    payload_raw = await r.spop(self.REDIS_QUEUE)
                    if not payload_raw:
                        self.logger.info("La cola de productos está vacía.")
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
                        
                    # Limpiar de la cola de procesamiento
                    await r.srem(self.REDIS_PROCESSING, payload_raw)
                    await r.sadd(self.REDIS_DONE, payload_raw)
                    
                await context.close()
                await browser.close()
        finally:
            await r.aclose()
            
        self.logger.info(f"Fase B finalizada. Productos extraídos guardados: {len(scraped_products)}")
        return scraped_products

    async def _process_product_url(self, context, url: str, sku: str) -> Optional[ScrapedProduct]:
        """Procesa una URL individual usando Playwright y retries."""
        max_retries = 3
        page = await context.new_page()
        
        for attempt in range(max_retries):
            self.logger.info(f"Leyendo URL (intento {attempt+1}/{max_retries}): {url}")
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                # Esperamos un poco para la carga dinámica de precios de Angular SSR
                await page.wait_for_timeout(4000)
                
                content = await page.content()
                soup = BeautifulSoup(content, "lxml")
                
                h1_tag = soup.find("h1")
                nombre = h1_tag.get_text(strip=True) if h1_tag else None
                if not nombre:
                    title_tag = soup.find("title")
                    nombre = title_tag.get_text(strip=True).replace(" | Farmatodo", "") if title_tag else "Sin Nombre"
                
                precio_raw = None
                
                # Intentamos extraer precios directamente del DOM con Playwright
                precio_raw = await page.evaluate('''() => {
                    const price_el = document.querySelector('div.product-purchase__price span') 
                                  || document.querySelector('.product-purchase__price--active') 
                                  || document.querySelector('.product-detail__mobile-price');
                    if (price_el) return price_el.innerText;
                    
                    // Fallback bs
                    const spans = Array.from(document.querySelectorAll('p, span, h2, h3'));
                    const bs_span = spans.find(el => el.innerText.includes('Bs.') && /\d/.test(el.innerText));
                    return bs_span ? bs_span.innerText : null;
                }''')
                
                if not nombre or not precio_raw:
                    self.logger.warning(f"Faltan datos básicos para {url}. Nombre: {nombre}, Precio: {precio_raw}")
                    raise ValueError("HTML no contiene datos o estructura cambió")
                    
                # Limpiar texto del precio y parsear → Decimal
                # Formatos posibles en VES: "Bs. 1.312,10", "Bs.636.30", "Bs 1.312.10"
                precio_limpio = precio_raw.replace("Bs.", "").replace("Bs", "").strip()
                # Remover posibles espacios internos y caracteres invisibles
                import re as _re
                precio_limpio = _re.sub(r'\s+', '', precio_limpio)
                try:
                    tiene_coma = "," in precio_limpio
                    tiene_punto = "." in precio_limpio
                    
                    if tiene_coma and tiene_punto:
                        # Formato VE estándar: 1.312,10  (punto=miles, coma=decimal)
                        # vs Formato US: 1,312.10 (coma=miles, punto=decimal)
                        if precio_limpio.rfind(",") > precio_limpio.rfind("."):
                            # Coma es el último separador → es decimal (VE standard)
                            precio_limpio = precio_limpio.replace(".", "").replace(",", ".")
                        else:
                            # Punto es el último separador → es decimal (US standard)
                            precio_limpio = precio_limpio.replace(",", "")
                    elif tiene_coma:
                        # Solo coma: puede ser decimal (636,30) o miles (1,312)
                        partes = precio_limpio.split(",")
                        if len(partes) == 2 and len(partes[1]) <= 2:
                            precio_limpio = precio_limpio.replace(",", ".")  # decimal
                        else:
                            precio_limpio = precio_limpio.replace(",", "")   # miles
                    elif tiene_punto:
                        puntos = precio_limpio.split(".")
                        if len(puntos) > 2:
                            # Múltiples puntos: 1.312.10 → el último segmento de 2 dígitos es decimal
                            if len(puntos[-1]) == 2:
                                entero = "".join(puntos[:-1])
                                precio_limpio = f"{entero}.{puntos[-1]}"
                            else:
                                # 1.000.000 → solo miles
                                precio_limpio = precio_limpio.replace(".", "")
                        # Si solo hay un punto y el segmento decimal tiene 3 dígitos → era miles
                        elif len(puntos) == 2 and len(puntos[1]) == 3:
                            precio_limpio = precio_limpio.replace(".", "")
                        # else: 636.30 → decimal normal, ok

                    precio_decimal = Decimal(precio_limpio)
                except Exception:
                    self.logger.warning(f"No se pudo parsear Decimal desde {precio_limpio}. fallback 0.0")
                    precio_decimal = Decimal("0.0")
                
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
                    self.logger.error("No se encontró ningún establecimiento Farmatodo en la DB. Inserta datos de prueba primero.")
                
        except Exception as e:
            self.logger.error(f"Error guardando en DB: {e}")
