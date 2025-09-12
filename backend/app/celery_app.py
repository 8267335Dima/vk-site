# backend/app/celery_app.py
from celery import Celery
from app.core.config import settings

# Определяем URL для Redis
redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

# Создаем и КОНФИГУРИРУЕМ экземпляр Celery здесь
celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.runner",
        "app.tasks.cron",
        "app.tasks.maintenance",
        "app.tasks.profile_parser"
    ]
)

# Дополнительно применяем конфигурацию через .conf для надежности
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
)