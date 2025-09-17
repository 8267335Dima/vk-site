# tests/tasks/logic/test_automation_jobs.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch
from datetime import datetime
import pytz

from app.db.models import User, Automation
from app.tasks.logic.automation_jobs import _run_daily_automations_async

pytestmark = pytest.mark.asyncio

# Настройки для 'Вечного онлайна'
ETERNAL_ONLINE_SETTINGS = {
    "mode": "schedule",
    "humanize": True,
    "schedule_weekly": {
        "1": {"is_active": True, "start_time": "09:00", "end_time": "18:00"}, # Понедельник
        "2": {"is_active": False, "start_time": "09:00", "end_time": "18:00"}, # Вторник
    }
}

@pytest.mark.parametrize(
    "mock_now_str, mock_random_val, should_run",
    [
        # Случай 1: Понедельник, 12:00. Внутри активного окна. Задача должна запуститься.
        ("2025-09-22 12:00:00", 0.5, True),
        # Случай 2: Понедельник, 08:00. Слишком рано. Задача НЕ должна запускаться.
        ("2025-09-22 08:00:00", 0.5, False),
        # Случай 3: Понедельник, 19:00. Слишком поздно. Задача НЕ должна запускаться.
        ("2025-09-22 19:00:00", 0.5, False),
        # Случай 4: Вторник, 12:00. День неактивен. Задача НЕ должна запускаться.
        ("2025-09-23 12:00:00", 0.5, False),
        # Случай 5: Понедельник, 12:00, но сработал "humanize skip". Задача НЕ должна запускаться.
        ("2025-09-22 12:00:00", 0.1, False), # random.random() вернет 0.1, что < 0.15
    ]
)
@patch('app.tasks.logic.automation_jobs._create_and_run_arq_task', new_callable=AsyncMock)
async def test_eternal_online_schedule_logic(
    mock_create_task: AsyncMock,
    db_session: AsyncSession,
    test_user: User,
    mocker,
    mock_now_str: str,
    mock_random_val: float,
    should_run: bool
):
    """
    Тест проверяет логику принятия решения о запуске задачи 'eternal_online'
    в зависимости от времени, дня недели и 'гуманизации'.
    """
    # Arrange:
    # 1. Создаем пользователя с активной автоматизацией 'eternal_online'
    automation = Automation(
        user_id=test_user.id,
        automation_type="eternal_online",
        is_active=True,
        settings=ETERNAL_ONLINE_SETTINGS
    )
    db_session.add(automation)
    await db_session.commit()

    # 2. Мокаем системные зависимости: время и случайность
    moscow_tz = pytz.timezone("Europe/Moscow")
    mock_now = moscow_tz.localize(datetime.strptime(mock_now_str, "%Y-%m-%d %H:%M:%S"))
    mocker.patch('app.tasks.logic.automation_jobs.datetime.datetime').now.return_value = mock_now
    mocker.patch('app.tasks.logic.automation_jobs.random.random', return_value=mock_random_val)
    
    # Мокаем Redis lock, чтобы он всегда "захватывался"
    mock_redis_client = AsyncMock()
    mock_redis_client.set.return_value = True
    mocker.patch('app.tasks.logic.automation_jobs.Redis.from_url', return_value=mock_redis_client)
    
    # Мокаем ARQ pool
    mocker.patch('app.tasks.logic.automation_jobs.create_pool', return_value=AsyncMock())
    
    # Act:
    await _run_daily_automations_async(automation_group='online')

    # Assert:
    if should_run:
        # Проверяем, что функция постановки задачи в очередь была вызвана
        mock_create_task.assert_awaited_once()
    else:
        # Проверяем, что функция постановки задачи в очередь НЕ была вызвана
        mock_create_task.assert_not_awaited()