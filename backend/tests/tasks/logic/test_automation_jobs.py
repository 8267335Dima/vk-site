# tests/tasks/logic/test_automation_jobs.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch
from datetime import datetime
import pytz
from datetime import datetime as real_datetime
from app.db.models import User, Automation
from app.tasks.logic.automation_jobs import _run_daily_automations_async
from app.core.enums import AutomationType

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
        ("2025-09-22 12:00:00", 0.5, True),
        ("2025-09-22 08:00:00", 0.5, False),
        ("2025-09-22 19:00:00", 0.5, False),
        ("2025-09-23 12:00:00", 0.5, False),
        ("2025-09-22 12:00:00", 0.1, False),
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
    automation = Automation(
        user_id=test_user.id,
        automation_type=AutomationType.ETERNAL_ONLINE,
        is_active=True,
        settings=ETERNAL_ONLINE_SETTINGS
    )
    db_session.add(automation)
    await db_session.commit()

    # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    # Мы мокируем только метод now(), а не весь класс datetime.
    # Это позволяет datetime.strptime() работать корректно.
    moscow_tz = pytz.timezone("Europe/Moscow")
    mock_now_in_moscow = moscow_tz.localize(datetime.strptime(mock_now_str, "%Y-%m-%d %H:%M:%S"))
    mock_now_in_utc = mock_now_in_moscow.astimezone(pytz.utc)
    
    mock_dt_module = mocker.patch('app.tasks.logic.automation_jobs.datetime')
    mock_dt_module.datetime.now.return_value = mock_now_in_utc
    mock_dt_module.datetime.strptime = real_datetime.strptime # Возвращаем настоящий strptime
    
    mocker.patch('app.tasks.logic.automation_jobs.random.random', return_value=mock_random_val)
    mock_arq_pool = AsyncMock()

    # Act:
    await _run_daily_automations_async(
        session=db_session,
        arq_pool=mock_arq_pool,
        automation_group='online'
    )

    # Assert:
    if should_run:
        mock_create_task.assert_awaited_once()
    else:
        mock_create_task.assert_not_awaited()