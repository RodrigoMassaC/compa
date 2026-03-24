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
    """Ejecuta una coroutine asyncio desde un task Celery (sync)."""
    return asyncio.run(coro)


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
        from app.services.scraper.spiders.central_madeirense_prices import MadeirensePriceSpider
        logger.info("run_madeirense_prices: iniciando...")
        _run_async(MadeirensePriceSpider().run())
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
