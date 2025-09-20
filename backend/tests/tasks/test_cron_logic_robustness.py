# tests/tasks/test_cron_logic_robustness.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from unittest.mock import patch

from app.db.models import Plan
from app.core.enums import PlanName
from app.tasks.logic.maintenance_jobs import _check_expired_plans_async

pytestmark = pytest.mark.anyio

async def test_check_expired_plans_handles_missing_expired_plan_in_db(db_session: AsyncSession):
    """
    Тест на отказоустойчивость: проверяет, что CRON-задача _check_expired_plans_async
    не падает, если в БД по какой-то причине отсутствует системный тариф 'EXPIRED'.
    """
    # Arrange:
    # 1. Намеренно удаляем тариф 'EXPIRED' из базы данных.
    stmt_delete = delete(Plan).where(Plan.name_id == PlanName.EXPIRED.name)
    await db_session.execute(stmt_delete)
    await db_session.commit()

    # 2. Убеждаемся, что его там действительно нет.
    stmt_select = select(Plan).where(Plan.name_id == PlanName.EXPIRED.name)
    plan_in_db = (await db_session.execute(stmt_select)).scalar_one_or_none()
    assert plan_in_db is None

    # Act & Assert:
    # 3. Мокаем логгер, чтобы проверить, что было записано критическое сообщение.
    with patch("app.tasks.logic.maintenance_jobs.log.critical") as mock_log_critical:
        # 4. Вызываем CRON-задачу. Мы ожидаем, что она не выбросит исключение.
        await _check_expired_plans_async(session=db_session)
        
        # 5. Проверяем, что в лог было записано сообщение о критической ошибке конфигурации.
        mock_log_critical.assert_called_once_with(
            "maintenance.fatal_error",
            message="Expired plan not found in the database. Cannot process expired users."
        )