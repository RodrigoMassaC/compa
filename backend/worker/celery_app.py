"""
Configuración de Celery para Compa.
Usa Redis como broker y backend de resultados.
Las tareas CRON se configuran con beat_schedule.
"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings


# Instancia de Celery con Redis como broker
celery_app = Celery(
    "compa_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks"],  # Módulo donde viven las tareas
)

# ── Configuración general ──
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Caracas",   # UTC-4 (Venezuela)
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,          # Resultados expiran en 1 hora
)

# ── Programación de tareas CRON ──
celery_app.conf.beat_schedule = {
    # Descargar tasa BCV cada día a las 6:00 AM hora de Caracas (UTC-4)
    # Las 6:00 AM VET = 10:00 AM UTC
    "fetch-bcv-rate-daily": {
        "task": "worker.tasks.fetch_bcv_rate",
        "schedule": crontab(hour=10, minute=0),  # UTC (= 6:00 AM UTC-4)
        "options": {"queue": "cron"},
    },
    "normalize-products-every-6-hours": {
        "task": "worker.tasks.normalize_pending_products",
        "schedule": crontab(minute=0, hour="*/6"), # Ejecutar en horas divisibles por 6 (0, 6, 12, 18)
    },
}
