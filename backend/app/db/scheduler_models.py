# backend/app/db/scheduler_models.py
"""
Этот файл содержит модели, необходимые для работы
библиотеки sqlalchemy-celery-beat.
Их нужно импортировать, чтобы Alembic мог их "увидеть"
и создать для них таблицы.
"""
# --- ИСПРАВЛЕНИЕ: Импорт из правильного, установленного пакета ---
from sqlalchemy_celery_beat.models import (
    PeriodicTask,
    IntervalSchedule,
    CrontabSchedule,
    SolarSchedule
)

__all__ = [
    'PeriodicTask',
    'IntervalSchedule',
    'CrontabSchedule',
    'SolarSchedule'
]