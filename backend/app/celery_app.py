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
    beat_dburi=settings.database_url.replace("+asyncpg", ""),
    
    # УЛУЧШЕНИЕ: Продакшн-настройки для повышения надежности и производительности
    # Гарантирует, что задача будет подтверждена только после ее успешного выполнения (или провала),
    # а не в момент получения воркером. Защищает от потери задач при сбое воркера.
    task_acks_late = True,

    # Оптимизация для I/O-bound задач (наши запросы к VK API).
    # Воркер будет брать только одну задачу за раз, что предотвращает "зависание"
    # других задач в его очереди, если текущая выполняется долго.
    worker_prefetch_multiplier = 1,
)