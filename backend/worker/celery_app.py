"""
Celery app de Compa — broker Redis, beat scheduler incluido.
El worker en docker-compose corre con --beat para ejecutar tareas programadas.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "compa",
    broker=settings.redis_url + "/0",
    backend=settings.redis_url + "/1",
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Caracas",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    # ⚠️  VPS de 2 vCPU: solo 1 tarea pesada a la vez (los spiders Playwright
    # son CPU-intensivos). Si subes a 2, dos spiders concurrentes saturan el VPS.
    worker_concurrency=1,
    task_acks_late=True,
    beat_schedule={
        # ── Tasa BCV cada hora ──────────────────────────────────────────────
        "actualizar-tasa-bcv": {
            "task": "worker.tasks.run_tasa_bcv",
            "schedule": crontab(minute=0, hour="*"),
        },

        # ── Catálogos y precios semanales (domingo) ─────────────────────────
        # Farmago
        "scrape-farmago-catalog": {
            "task": "worker.tasks.run_farmago_catalog",
            "schedule": crontab(minute=0, hour=2, day_of_week=0),
        },
        "scrape-farmago-prices": {
            "task": "worker.tasks.run_farmago_prices",
            "schedule": crontab(minute=0, hour=4, day_of_week=0),
        },
        # Locatel
        "scrape-locatel-catalog": {
            "task": "worker.tasks.run_locatel_catalog",
            "schedule": crontab(minute=0, hour=6, day_of_week=0),
        },
        "scrape-locatel-prices": {
            "task": "worker.tasks.run_locatel_prices",
            "schedule": crontab(minute=0, hour=8, day_of_week=0),
        },
        # Central Madeirense
        "scrape-madeirense-catalog": {
            "task": "worker.tasks.run_madeirense_catalog",
            "schedule": crontab(minute=0, hour=10, day_of_week=0),
        },
        "scrape-madeirense-prices": {
            "task": "worker.tasks.run_madeirense_prices",
            "schedule": crontab(minute=0, hour=12, day_of_week=0),
        },
        # Excelsior Gama
        "scrape-gama-catalog": {
            "task": "worker.tasks.run_gama_catalog",
            "schedule": crontab(minute=0, hour=14, day_of_week=0),
        },
        "scrape-gama-prices": {
            "task": "worker.tasks.run_gama_prices",
            "schedule": crontab(minute=0, hour=16, day_of_week=0),
        },

        # ── Farmatodo mensual (día 1 del mes) ───────────────────────────────
        # Fase A+B del catálogo (descubre productos nuevos y actualiza los existentes)
        "scrape-farmatodo-catalog-monthly": {
            "task": "worker.tasks.run_farmatodo_catalog",
            "schedule": crontab(minute=0, hour=2, day_of_month=1),
        },
        # Precios (visita cada producto y extrae el precio actual)
        "scrape-farmatodo-prices-monthly": {
            "task": "worker.tasks.run_farmatodo_prices",
            "schedule": crontab(minute=0, hour=6, day_of_month=1),
        },

        # ── Normalizador IA diario (3 AM) ───────────────────────────────────
        # Procesa productos nuevos en estado PENDIENTE.
        # Si no hay pendientes, termina inmediatamente sin gasto de API.
        "normalizar-pendientes": {
            "task": "worker.tasks.run_normalizador",
            "schedule": crontab(minute=0, hour=3),
        },

        # ── Refrescar embeddings cada 10 min ────────────────────────────────
        # Genera embeddings para productos nuevos o modificados.
        # Costo despreciable (~$0.000001 por producto).
        "refrescar-embeddings": {
            "task": "worker.tasks.refrescar_embeddings",
            "schedule": crontab(minute="*/10"),
        },
    },
)
