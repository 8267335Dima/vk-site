# tests/tasks/test_cron_robustness.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, call

from app.db.models import User
from app.tasks.logic.analytics_jobs import _snapshot_all_users_metrics_async

pytestmark = pytest.mark.anyio

async def test_snapshot_metrics_continues_after_user_error(
    db_session: AsyncSession, test_user: User
):
    """
    Тест на отказоустойчивость: CRON-задача по сбору метрик должна
    продолжать работу, даже если на одном из пользователей произошла ошибка.
    """
    # Arrange:
    # 1. Создаем второго пользователя.
    another_user = User(vk_id=999, encrypted_vk_token="token2")
    db_session.add(another_user)
    await db_session.commit()

    # 2. Мокаем ProfileAnalyticsService так, чтобы он падал на первом
    #    пользователе (test_user) и успешно отрабатывал на втором (another_user).
    with patch('app.tasks.logic.analytics_jobs.ProfileAnalyticsService') as MockService:
        mock_instance = MockService.return_value
        
        # Настраиваем разное поведение для разных вызовов
        async def mock_snapshot(*args, **kwargs):
            # `self.user` будет разным для каждого экземпляра сервиса
            if mock_instance.user.vk_id == test_user.vk_id:
                raise ValueError("Simulated processing error for first user")
            else:
                return "Success" # Успешное выполнение для второго пользователя

        mock_instance.snapshot_profile_metrics = AsyncMock(side_effect=mock_snapshot)
        
        # 3. Мокаем логгер, чтобы убедиться, что ошибка была записана.
        with patch("app.tasks.logic.analytics_jobs.log.error") as mock_log_error:
            # Act:
            # 4. Запускаем CRON-задачу.
            await _snapshot_all_users_metrics_async(session=db_session)
            
            # Assert:
            # 5. Проверяем, что snapshot_profile_metrics был вызван для ОБОИХ пользователей.
            assert mock_instance.snapshot_profile_metrics.call_count == 2
            
            # 6. Проверяем, что ошибка для первого пользователя была залогирована.
            mock_log_error.assert_called_once()
            _, log_kwargs = mock_log_error.call_args
            assert log_kwargs['user_id'] == test_user.id
            assert "Simulated processing error" in log_kwargs['error']