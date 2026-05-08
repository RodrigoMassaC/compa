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

# JS que busca TODOS los indicadores de "no disponible" en el bloque del producto
INSPECT_JS = """
() => {
    const result = {
        json_ld_price: null,
        json_ld_currency: null,
        json_ld_availability: null,
        boton_carrito: null,
        texto_no_disponible_main: null,
        elementos_no_disponible: [],
        clases_sospechosas: [],
        all_buttons: [],
    };

    // JSON-LD
    const ld = document.querySelector('script[type="application/ld+json"]');
    if (ld) {
        try {
            const data = JSON.parse(ld.textContent);
            const offer = data.offers || {};
            result.json_ld_price = offer.price || null;
            result.json_ld_currency = offer.priceCurrency || null;
            result.json_ld_availability = offer.availability || null;
        } catch (e) {}
    }

    // Solo el bloque del producto principal
    const purchaseBlock = document.querySelector('.product-purchase, [class*="product-purchase"]')
                       || document.querySelector('[class*="product-detail"]')
                       || document.body;

    // Buscar texto de no disponibilidad SOLO en el bloque principal
    const mainText = (purchaseBlock.innerText || '').toLowerCase();
    const frasesNoDisp = ['no disponible', 'agotado', 'sin existencia', 'sin stock',
                          'producto no disponible', 'out of stock', 'notifícame',
                          'avísame cuando', 'temporalmente no'];
    for (const frase of frasesNoDisp) {
        if (mainText.includes(frase)) {
            result.texto_no_disponible_main = frase;
            break;
        }
    }

    // Cualquier elemento con clases que sugieren "no disponible"
    const susClassRegex = /unavailable|not-available|sold-out|out-of-stock|no-disponible|agotad/i;
    purchaseBlock.querySelectorAll('*').forEach(el => {
        const cls = el.className || '';
        if (typeof cls === 'string' && susClassRegex.test(cls)) {
            result.clases_sospechosas.push({
                class: cls,
                text: (el.innerText || '').trim().slice(0, 80),
            });
        }
    });

    // Todos los botones visibles del bloque principal
    purchaseBlock.querySelectorAll('button').forEach(btn => {
        result.all_buttons.push({
            class: btn.className,
            text: (btn.innerText || '').trim().slice(0, 60),
            disabled: btn.disabled,
        });
    });

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

                print(f"\n💰 JSON-LD price:        {data.get('json_ld_price')} {data.get('json_ld_currency')}")
                print(f"📦 JSON-LD availability: {data.get('json_ld_availability')}")
                print(f"\n⚠️  Texto 'no disponible' en bloque principal: {data.get('texto_no_disponible_main')!r}")

                clases = data.get('clases_sospechosas', [])
                print(f"\n🔍 Elementos con clases sospechosas ({len(clases)}):")
                for c in clases[:10]:
                    print(f"   class='{c['class']}'  texto='{c['text']}'")

                print(f"\n🔘 Botones del bloque principal:")
                for b in data.get('all_buttons', []):
                    flag = ' [DISABLED]' if b['disabled'] else ''
                    print(f"   class='{b['class']}'{flag}")
                    print(f"     texto='{b['text']}'")

            except Exception as e:
                print(f"❌ Error: {e}")
            finally:
                await page.close()
                await asyncio.sleep(2)

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
