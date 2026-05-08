"""
farmatodo_prices.py
Fase B del spider de Farmatodo: recorre los registros de productos_crudos
que ya tienen url_origen, visita cada URL con Playwright, extrae el precio
actual y lo inserta en historial_precios.

Uso como tarea Celery (worker/tasks.py):
    from app.services.scraper.spiders.farmatodo_prices import FarmatodoPriceSpider
    spider = FarmatodoPriceSpider()
    await spider.run()

Uso directo:
    python -m app.services.scraper.spiders.farmatodo_prices
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


# JavaScript que extrae el precio del DOM renderizado de Farmatodo (Angular 12).
# Prueba selectores conocidos en orden y hace fallback a búsqueda por texto "Bs.".
PRICE_JS = """
() => {
    const selectors = [
        'div.product-purchase__price span',
        '.product-purchase__price--active',
        '.product-detail__mobile-price',
        '.cont-price span',
        '.price-tag',
        '.product-price'
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.trim()) return el.innerText.trim();
    }
    // Fallback: nodo hoja que contenga "Bs" y un dígito
    const all = Array.from(document.querySelectorAll('p, span, h2, h3, div'));
    const bs_el = all.find(el =>
        el.children.length === 0 &&
        el.innerText.includes('Bs') &&
        /\\d/.test(el.innerText)
    );
    return bs_el ? bs_el.innerText.trim() : null;
}
"""


def _parse_precio(raw: str) -> Optional[Decimal]:
    """
    Convierte texto de precio venezolano a Decimal.
    Maneja formatos: 'Bs. 1.312,10', 'Bs.636.30', 'Bs 1312.10', 'Bs1.562,30', etc.

    El formato venezolano oficial es: punto = miles, coma = decimal
    (ej. 1.562,30 = mil quinientos sesenta y dos con treinta).
    """
    try:
        # Limpiar prefijos y sufijos comunes
        limpio = raw.replace("Bs.", "").replace("Bs", "").replace("BS", "").replace("bs", "")
        # Eliminar espacios incluso non-breaking ( ) y otros invisibles
        limpio = re.sub(r"[\s ​ ]+", "", limpio)
        # Eliminar cualquier caracter no numérico al inicio/final
        limpio = re.sub(r"^[^\d]+|[^\d]+$", "", limpio)

        if not limpio:
            return None

        tiene_coma = "," in limpio
        tiene_punto = "." in limpio

        if tiene_coma and tiene_punto:
            # Mirar cuál separador aparece de último — ese es el decimal
            if limpio.rfind(",") > limpio.rfind("."):
                # Formato VE: 1.562,30 → punto=miles, coma=decimal
                limpio = limpio.replace(".", "").replace(",", ".")
            else:
                # Formato US: 1,562.30 → coma=miles, punto=decimal
                limpio = limpio.replace(",", "")
        elif tiene_coma:
            partes = limpio.split(",")
            if len(partes) == 2 and len(partes[1]) <= 2:
                # 156,23 → decimal venezolano
                limpio = limpio.replace(",", ".")
            else:
                # 1,562 → miles US (sin decimal)
                limpio = limpio.replace(",", "")
        elif tiene_punto:
            puntos = limpio.split(".")
            if len(puntos) > 2:
                # Múltiples puntos: 1.562.30 (raro). Tomar último como decimal si tiene 2 dígitos
                if len(puntos[-1]) == 2:
                    limpio = "".join(puntos[:-1]) + "." + puntos[-1]
                else:
                    limpio = limpio.replace(".", "")
            elif len(puntos) == 2 and len(puntos[1]) == 3:
                # 1.000 → tres dígitos después del punto = miles
                limpio = limpio.replace(".", "")
            # Si len(puntos[1]) <= 2 dejamos como está (formato decimal estándar)

        return Decimal(limpio)
    except (InvalidOperation, Exception):
        return None


class FarmatodoPriceSpider(BaseSpider):
    """
    Fase B del spider de Farmatodo.
    Lee productos_crudos de Farmatodo con url_origen, extrae el precio
    actual de cada página de producto con Playwright y lo guarda en historial_precios.
    """

    BATCH_SIZE = 10
    DELAY_MIN = 3.0
    DELAY_MAX = 5.0
    PAUSA_CADA_N = 150   # pausa extra cada 150 productos
    PAUSA_SEGUNDOS = 20  # pausa de 20s para que el rate limit se "enfríe"

    # ── Helpers de datos ─────────────────────────────────────────────────────

    async def _get_productos(self) -> list:
        """Retorna filas (id_producto_crudo, url_origen) de Farmatodo con URL
        que aún no tienen precio registrado en historial_precios."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("""
                SELECT pc.id_producto_crudo, pc.url_origen
                FROM productos_crudos pc
                JOIN establecimientos e ON e.id_establecimiento = pc.id_establecimiento
                JOIN cadenas_comerciales c ON c.id_cadena = e.id_cadena
                LEFT JOIN historial_precios hp ON hp.id_producto_crudo = pc.id_producto_crudo
                WHERE c.nombre_cadena = 'Farmatodo'
                  AND pc.url_origen IS NOT NULL
                  AND hp.id_producto_crudo IS NULL
                ORDER BY pc.creado_en DESC
            """))
            return result.fetchall()

    async def _save_precio(self, id_producto_crudo, precio_bruto_ves: Decimal) -> None:
        """Convierte VES → USD con tasa BCV vigente y guarda como USD.

        Razón: Farmatodo actualiza sus precios VES diariamente según la tasa
        BCV. Si guardamos en VES, mañana la conversión a USD da un valor
        distinto al real cuando cambia la tasa. Guardando en USD al momento
        del scraping, el valor queda "anclado" al precio real del producto.
        """
        async with AsyncSessionLocal() as session:
            # Obtener la tasa BCV vigente
            r = await session.execute(text("""
                SELECT valor_usd FROM historico_tasa_bcv
                ORDER BY fecha DESC LIMIT 1
            """))
            tasa = r.scalar()

            if not tasa or tasa <= 0:
                # Fallback: si no hay tasa, guardamos en VES para no perder dato
                logger.warning(
                    "No hay tasa BCV vigente — guardando precio en VES como fallback"
                )
                await session.execute(text("""
                    INSERT INTO historial_precios
                        (id_producto_crudo, precio_bruto, moneda_origen, fuente_datos)
                    VALUES
                        (:id_crudo, :precio, 'VES', 'SCRAPING_WEB')
                """), {"id_crudo": str(id_producto_crudo), "precio": precio_bruto_ves})
                await session.commit()
                return

            # Convertir a USD
            precio_usd = (Decimal(str(precio_bruto_ves)) / Decimal(str(tasa))).quantize(
                Decimal("0.0001")
            )
            await session.execute(text("""
                INSERT INTO historial_precios
                    (id_producto_crudo, precio_bruto, moneda_origen, fuente_datos)
                VALUES
                    (:id_crudo, :precio, 'USD', 'SCRAPING_WEB')
            """), {"id_crudo": str(id_producto_crudo), "precio": precio_usd})
            await session.commit()

    # ── Extracción Playwright ─────────────────────────────────────────────────

    async def _extract_price(self, page, url: str) -> Optional[Decimal]:
        """Visita la URL del producto y extrae el precio con JS evaluation.

        Loggea SIEMPRE el texto crudo extraído del DOM para diagnóstico — así
        si el parser falla podemos detectarlo en logs.
        """
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4000)   # Angular SSR delay

            precio_raw = await page.evaluate(PRICE_JS)
            if not precio_raw:
                self.logger.warning(f"  ⚠️  Precio no encontrado en DOM: {url}")
                return None

            precio = _parse_precio(precio_raw)
            if precio is None:
                self.logger.warning(
                    f"  ⚠️  No se pudo parsear precio raw='{precio_raw}' (chars: {[c for c in precio_raw[:40]]}) → {url}"
                )
                return None

            # Filtro placeholder absoluto
            if precio < Decimal("1"):
                self.logger.warning(
                    f"  ⚠️  Precio placeholder ({precio} Bs, raw='{precio_raw}') descartado: {url}"
                )
                return None

            # Log diagnóstico: mostrar texto crudo + valor parseado
            self.logger.debug(f"  💰 raw='{precio_raw}' → {precio} Bs ← {url}")

            return precio

        except Exception as e:
            self.logger.error(f"  ❌ Error visitando {url}: {e}")
            return None

    # ── Runner principal ──────────────────────────────────────────────────────

    async def run(self) -> List[ScrapedProduct]:
        """
        Punto de entrada del spider.
        Retorna lista vacía (los precios se persisten directamente en DB).
        """
        self.logger.info("🕷️  FarmatodoPriceSpider iniciando...")

        productos = await self._get_productos()
        total = len(productos)

        if not total:
            self.logger.warning(
                "⚠️  No hay productos_crudos con url_origen para Farmatodo. "
                "Ejecuta primero FarmatodoIndexSpider + FarmatodoDetailSpider."
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

                    await self._random_delay()   # delay anti-detección de BaseSpider

                self.logger.info(
                    f"  → Lote {lote_idx + 1} finalizado: "
                    f"✅ {extraidos} extraídos / ❌ {fallados} fallados"
                )

                # Pausa larga cada PAUSA_CADA_N productos (anti-bloqueo IP)
                total_procesado = extraidos + fallados
                if total_procesado > 0 and total_procesado % self.PAUSA_CADA_N == 0:
                    self.logger.info(
                        f"⏸️  Pausa anti-bloqueo: {self.PAUSA_SEGUNDOS}s tras {total_procesado} productos..."
                    )
                    await asyncio.sleep(self.PAUSA_SEGUNDOS)

            await context.close()
            await browser.close()

        self.logger.info(
            f"\n🏁 Spider finalizado — "
            f"✅ Extraídos: {extraidos}  ❌ Fallados: {fallados}  Total: {total}"
        )
        return []   # Los precios ya fueron persistidos directamente


# ── Punto de entrada directo ───────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    async def _main():
        spider = FarmatodoPriceSpider()
        await spider.run()

    asyncio.run(_main())
