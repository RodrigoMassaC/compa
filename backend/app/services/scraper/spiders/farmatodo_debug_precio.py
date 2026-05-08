"""
Script de DEBUG: visita 3 productos outliers de Farmatodo e inspecciona
todos los elementos del DOM relacionados con precio. Muestra el HTML crudo
para identificar exactamente qué selector está agarrando un precio incorrecto.

Uso:
    python -m app.services.scraper.spiders.farmatodo_debug_precio
"""
import asyncio
import logging

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("DebugFarmatodo")

# 3 productos outlier confirmados (los podemos cambiar si queremos otros)
URLS_DEBUG = [
    "https://www.farmatodo.com.ve/producto/111971865-margarina-mavesa-250gr",
    "https://www.farmatodo.com.ve/producto/111940228-hisopos-steritex-100unid",
    "https://www.farmatodo.com.ve/producto/112784381-jabon-en-barra-lux-rosas-francesas",
]

# JS que extrae JSON-LD + availability + indicadores de stock
INSPECT_JS = """
() => {
    const result = {
        json_ld_price: null,
        json_ld_currency: null,
        json_ld_availability: null,
        json_ld_full: null,
        bs_elements_main: [],
        boton_carrito: null,
        texto_agotado: false,
    };

    // JSON-LD structured data
    const ld = document.querySelector('script[type="application/ld+json"]');
    if (ld) {
        try {
            const data = JSON.parse(ld.textContent);
            const offer = data.offers || {};
            result.json_ld_price = offer.price || null;
            result.json_ld_currency = offer.priceCurrency || null;
            result.json_ld_availability = offer.availability || null;
            result.json_ld_full = JSON.stringify(data).slice(0, 1500);
        } catch (e) {
            result.json_ld_full = 'PARSE ERROR: ' + e.message;
        }
    }

    // Botón "Agregar al carrito" — si está disabled o no existe, sin stock
    const btnCart = document.querySelector('button[class*="cart"], button[class*="add"], [class*="add-to-cart"]');
    if (btnCart) {
        result.boton_carrito = {
            disabled: btnCart.disabled || btnCart.classList.contains('disabled'),
            text: (btnCart.innerText || '').trim().slice(0, 60),
        };
    }

    // Texto "agotado" / "sin stock" en cualquier parte
    const bodyText = (document.body.innerText || '').toLowerCase();
    result.texto_agotado = bodyText.includes('agotado') ||
                           bodyText.includes('sin stock') ||
                           bodyText.includes('no disponible') ||
                           bodyText.includes('out of stock');

    // Elementos con precio del bloque principal
    const purchaseBlock = document.querySelector('.product-purchase, [class*="product-purchase"]');
    if (purchaseBlock) {
        const all = purchaseBlock.querySelectorAll('*');
        for (const el of all) {
            const text = el.innerText || '';
            if (text.includes('Bs') && /\\d/.test(text) && el.children.length === 0 && text.length < 80) {
                result.bs_elements_main.push({
                    class: el.className,
                    text: text.trim(),
                });
            }
        }
    }

    return result;
}
"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )

        for url in URLS_DEBUG:
            page = await context.new_page()
            print(f"\n{'='*80}")
            print(f"URL: {url}")
            print('='*80)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(5000)  # esperar Angular

                data = await page.evaluate(INSPECT_JS)

                print(f"\n💰 JSON-LD price:        {data.get('json_ld_price')}")
                print(f"💰 JSON-LD currency:     {data.get('json_ld_currency')}")
                print(f"📦 JSON-LD availability: {data.get('json_ld_availability')}")
                print(f"🛒 Botón carrito:        {data.get('boton_carrito')}")
                print(f"⚠️  Texto agotado:        {data.get('texto_agotado')}")
                print(f"\n📊 Elementos 'Bs' del bloque PRINCIPAL ({len(data.get('bs_elements_main', []))}):")
                for i, el in enumerate(data.get('bs_elements_main', [])):
                    print(f"  [{i+1}] class='{el['class']}'  →  {el['text']}")
                print(f"\n📊 JSON-LD full (truncado):\n{data.get('json_ld_full')}")

            except Exception as e:
                print(f"❌ Error: {e}")
            finally:
                await page.close()
                await asyncio.sleep(2)

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
