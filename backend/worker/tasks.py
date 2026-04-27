"""
Tareas Celery de Compa.
Cada tarea wrappea un spider async dentro de asyncio.run()
para ser compatible con el worker síncrono de Celery.
"""
import asyncio
import logging

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Ejecuta una coroutine asyncio desde un task Celery (sync).
    Crea un loop nuevo para evitar conflictos con loops previos."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Tasa BCV ─────────────────────────────────────────────────────────────────

@celery_app.task(name="worker.tasks.run_tasa_bcv", bind=True, max_retries=3)
def run_tasa_bcv(self):
    """Actualiza la tasa BCV desde la fuente oficial."""
    try:
        from app.services.scraper.spiders.tasa_bcv import actualizar_tasa_bcv
        _run_async(actualizar_tasa_bcv())
        logger.info("run_tasa_bcv: completado")
    except ImportError:
        # Spider de tasa BCV aún no implementado — skip silencioso
        logger.warning("run_tasa_bcv: spider no disponible, skip")
    except Exception as exc:
        logger.error("run_tasa_bcv falló: %s", exc)
        raise self.retry(exc=exc, countdown=60)


# ── Price Scrapers ────────────────────────────────────────────────────────────

@celery_app.task(name="worker.tasks.run_farmago_prices", bind=True, max_retries=2)
def run_farmago_prices(self):
    """Actualiza precios de Farmago."""
    try:
        from app.services.scraper.spiders.farmago_prices import FarmagoPriceSpider
        logger.info("run_farmago_prices: iniciando...")
        _run_async(FarmagoPriceSpider().run())
        logger.info("run_farmago_prices: completado")
    except Exception as exc:
        logger.error("run_farmago_prices falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="worker.tasks.run_farmatodo_prices", bind=True, max_retries=2)
def run_farmatodo_prices(self):
    """Actualiza precios de Farmatodo."""
    try:
        from app.services.scraper.spiders.farmatodo_prices import FarmatodoPriceSpider
        logger.info("run_farmatodo_prices: iniciando...")
        _run_async(FarmatodoPriceSpider().run())
        logger.info("run_farmatodo_prices: completado")
    except Exception as exc:
        logger.error("run_farmatodo_prices falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="worker.tasks.run_madeirense_prices", bind=True, max_retries=2)
def run_madeirense_prices(self):
    """Actualiza precios de Central Madeirense."""
    try:
        from app.services.scraper.spiders.central_madeirense_prices import CentralMadeirensePriceSpider
        logger.info("run_madeirense_prices: iniciando...")
        _run_async(CentralMadeirensePriceSpider().run())
        logger.info("run_madeirense_prices: completado")
    except Exception as exc:
        logger.error("run_madeirense_prices falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="worker.tasks.run_locatel_prices", bind=True, max_retries=2)
def run_locatel_prices(self):
    """Actualiza precios de Locatel."""
    try:
        from app.services.scraper.spiders.locatel_prices import LocatelPriceSpider
        logger.info("run_locatel_prices: iniciando...")
        _run_async(LocatelPriceSpider().run())
        logger.info("run_locatel_prices: completado")
    except Exception as exc:
        logger.error("run_locatel_prices falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


# ── Catalog Scrapers (Fase A) ────────────────────────────────────────────────

@celery_app.task(name="worker.tasks.run_farmatodo_catalog", bind=True, max_retries=1)
def run_farmatodo_catalog(self):
    """Indexa catálogo de Farmatodo (Fase A: sitemap + Fase B: detalles paralelos)."""
    try:
        from app.services.scraper.spiders.farmatodo import FarmatodoIndexSpider, FarmatodoDetailSpider
        logger.info("run_farmatodo_catalog: Fase A (sitemap)...")
        _run_async(FarmatodoIndexSpider().run())
        logger.info("run_farmatodo_catalog: Fase B (detail paralelo, %d workers)...",
                     FarmatodoDetailSpider.CONCURRENCY)
        _run_async(FarmatodoDetailSpider().run())
        logger.info("run_farmatodo_catalog: completado")
    except Exception as exc:
        logger.error("run_farmatodo_catalog falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="worker.tasks.run_farmatodo_detail", bind=True, max_retries=1)
def run_farmatodo_detail(self):
    """Corre solo Fase B de Farmatodo (útil si Fase A ya cargó el sitemap en Redis)."""
    try:
        from app.services.scraper.spiders.farmatodo import FarmatodoDetailSpider
        logger.info("run_farmatodo_detail: Fase B only...")
        _run_async(FarmatodoDetailSpider().run())
        logger.info("run_farmatodo_detail: completado")
    except Exception as exc:
        logger.error("run_farmatodo_detail falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="worker.tasks.run_locatel_catalog", bind=True, max_retries=1)
def run_locatel_catalog(self):
    """Indexa catálogo de Locatel (Fase A + B)."""
    try:
        from app.services.scraper.spiders.locatel import LocatelIndexSpider, LocatelDetailSpider
        logger.info("run_locatel_catalog: Fase A (index)...")
        _run_async(LocatelIndexSpider().run())
        logger.info("run_locatel_catalog: Fase B (detail)...")
        _run_async(LocatelDetailSpider().run())
        logger.info("run_locatel_catalog: completado")
    except Exception as exc:
        logger.error("run_locatel_catalog falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="worker.tasks.run_gama_catalog", bind=True, max_retries=1)
def run_gama_catalog(self):
    """Indexa catálogo de Excelsior Gama (Fase A + B)."""
    try:
        from app.services.scraper.spiders.gama import GamaIndexSpider, GamaDetailSpider
        logger.info("run_gama_catalog: Fase A (index)...")
        _run_async(GamaIndexSpider().run())
        logger.info("run_gama_catalog: Fase B (detail)...")
        _run_async(GamaDetailSpider().run())
        logger.info("run_gama_catalog: completado")
    except Exception as exc:
        logger.error("run_gama_catalog falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="worker.tasks.run_farmago_catalog", bind=True, max_retries=1)
def run_farmago_catalog(self):
    """Indexa catálogo de Farmago (descubre productos y guarda con URL)."""
    try:
        from app.services.scraper.spiders.farmago import FarmagoSpider
        logger.info("run_farmago_catalog: iniciando...")
        _run_async(FarmagoSpider().run())
        logger.info("run_farmago_catalog: completado")
    except Exception as exc:
        logger.error("run_farmago_catalog falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="worker.tasks.run_madeirense_catalog", bind=True, max_retries=1)
def run_madeirense_catalog(self):
    """Indexa catálogo de Central Madeirense (descubre productos y guarda con URL)."""
    try:
        from app.services.scraper.spiders.central_madeirense import CentralMadeirenSeSpider
        logger.info("run_madeirense_catalog: iniciando...")
        _run_async(CentralMadeirenSeSpider().run())
        logger.info("run_madeirense_catalog: completado")
    except Exception as exc:
        logger.error("run_madeirense_catalog falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="worker.tasks.run_gama_prices", bind=True, max_retries=2)
def run_gama_prices(self):
    """Refresca precios de productos de Excelsior Gama (visita cada URL conocida)."""
    try:
        from app.services.scraper.spiders.gama_prices import GamaPriceSpider
        logger.info("run_gama_prices: iniciando...")
        _run_async(GamaPriceSpider().run())
        logger.info("run_gama_prices: completado")
    except Exception as exc:
        logger.error("run_gama_prices falló: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="worker.tasks.run_normalizador", bind=True, max_retries=1)
def run_normalizador(self):
    """Corre el normalizador IA sobre productos en estado PENDIENTE."""
    try:
        from app.services.normalizador.normalizer import NormalizadorIA
        logger.info("run_normalizador: iniciando...")
        _run_async(NormalizadorIA().run(batch_size=20))
        logger.info("run_normalizador: completado")
    except Exception as exc:
        logger.error("run_normalizador falló: %s", exc)
        raise self.retry(exc=exc, countdown=600)
