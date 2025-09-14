# backend/app/celery_app.py
from celery import Celery
from app.core.config import settings

redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url
)

celery_app.conf.broker_url = redis_url
celery_app.conf.result_backend = redis_url

celery_app.conf.task_routes = {
    'app.tasks.cron.*': {'queue': 'default'},
    'app.tasks.maintenance.*': {'queue': 'low_priority'},
    'app.tasks.profile_parser.*': {'queue': 'low_priority'},
}

celery_app.conf.update(
    task_track_started=True,
    task_default_queue='default',
    
    # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Указываем использовать наш кастомный планировщик ---
    beat_scheduler='app.tasks.scheduler.DatabaseScheduler',
    # -------------------------------------------------------------------------

    task_acks_late = True,
    worker_prefetch_multiplier = 1,
)