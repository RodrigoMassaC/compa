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
    task_acks_late=True,
    beat_schedule={
        "actualizar-tasa-bcv": {
            "task": "worker.tasks.run_tasa_bcv",
            "schedule": crontab(minute=0, hour="*"),
        },
        "scrape-farmago-prices": {
            "task": "worker.tasks.run_farmago_prices",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "scrape-farmatodo-prices": {
            "task": "worker.tasks.run_farmatodo_prices",
            "schedule": crontab(minute=15, hour="*/6"),
        },
        "scrape-madeirense-prices": {
            "task": "worker.tasks.run_madeirense_prices",
            "schedule": crontab(minute=30, hour="*/6"),
        },
        "scrape-locatel-prices": {
            "task": "worker.tasks.run_locatel_prices",
            "schedule": crontab(minute=45, hour="*/6"),
        },
    },
)
