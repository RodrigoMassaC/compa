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

# JS que extrae TODOS los elementos con "Bs" en el texto y sus selectores
INSPECT_JS = """
() => {
    const result = {
        all_bs_elements: [],
        meta_price: null,
        json_ld: null,
    };

    // Todos los elementos con "Bs" en su texto
    const all = document.querySelectorAll('*');
    for (const el of all) {
        const text = el.innerText || '';
        if (text.includes('Bs') && /\\d/.test(text) && el.children.length === 0 && text.length < 100) {
            result.all_bs_elements.push({
                tag: el.tagName,
                class: el.className,
                id: el.id,
                text: text.trim(),
            });
        }
    }

    // Meta tags con price
    const meta = document.querySelector('meta[property="product:price:amount"], meta[itemprop="price"]');
    if (meta) result.meta_price = meta.getAttribute('content');

    // JSON-LD structured data
    const ld = document.querySelector('script[type="application/ld+json"]');
    if (ld) {
        try {
            const data = JSON.parse(ld.textContent);
            result.json_ld = JSON.stringify(data).slice(0, 500);
        } catch (e) {}
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

                print(f"\n📊 Meta price: {data['meta_price']}")
                print(f"\n📊 JSON-LD: {data['json_ld']}\n")

                print(f"📊 Elementos con 'Bs' encontrados: {len(data['all_bs_elements'])}\n")
                for i, el in enumerate(data['all_bs_elements'][:15]):
                    print(f"  [{i+1}] <{el['tag']} class='{el['class']}' id='{el['id']}'>")
                    print(f"       texto: '{el['text']}'")

            except Exception as e:
                print(f"❌ Error: {e}")
            finally:
                await page.close()
                await asyncio.sleep(2)

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
