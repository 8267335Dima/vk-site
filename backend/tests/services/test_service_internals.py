# tests/services/test_service_internals.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import time
import datetime

from app.services.humanizer import Humanizer
from app.services.event_emitter import SystemLogEmitter
from app.db.models import DelayProfile, Notification

pytestmark = pytest.mark.anyio

class TestHumanizerInternals:

    @pytest.mark.parametrize("hour, expected_factor", [
        (3, 0.8),   # Ночь
        (8, 1.1),   # Утро
        (15, 1.0),  # День
        (20, 1.25)  # Вечер
    ])
    def test_get_time_of_day_factor(self, mocker, hour, expected_factor):
        """Тест: проверяет, что множитель задержки правильно меняется от времени суток."""
        # Мокаем `datetime.now()` чтобы вернуть нужное время
        mock_now = datetime.datetime.now().replace(hour=hour)
        mocker.patch('datetime.datetime', MagicMock(now=lambda: mock_now))
        
        humanizer = Humanizer(DelayProfile.normal, AsyncMock())
        assert humanizer._get_time_of_day_factor() == expected_factor

    def test_get_fatigue_factor(self, mocker):
        """Тест: проверяет, что 'усталость' (задержка) растет со временем и количеством действий."""
        # Мокаем `time.time()`
        mock_time = mocker.patch('time.time')
        
        humanizer = Humanizer(DelayProfile.normal, AsyncMock())
        
        # Начало сессии
        mock_time.return_value = 1000.0
        humanizer.session_start_time = 1000.0
        humanizer.actions_in_session = 0
        factor1 = humanizer._get_fatigue_factor()
        assert factor1 == 1.0

        # После 10 действий и 5 минут
        humanizer.actions_in_session = 10
        mock_time.return_value = 1000.0 + (5 * 60) # +5 минут
        factor2 = humanizer._get_fatigue_factor()
        assert factor2 > factor1

class TestSystemLogEmitter:

    async def test_send_log_maps_status_to_logger_method(self, mocker):
        """Тест: проверяет, что эмиттер вызывает правильный метод логгера."""
        mock_logger = MagicMock()
        mocker.patch('structlog.get_logger', return_value=mock_logger)
        
        emitter = SystemLogEmitter(task_name="test_task")
        
        await emitter.send_log("info message", "info")
        mock_logger.info.assert_called_once_with("info message", url=None, status_from_emitter="info")
        
        await emitter.send_log("error message", "error")
        mock_logger.error.assert_called_once_with("error message", url=None, status_from_emitter="error")
        
    async def test_send_system_notification_creates_db_entry(self, db_session):
        """Тест: проверяет, что эмиттер создает запись Notification в БД."""
        emitter = SystemLogEmitter(task_name="test_task")
        emitter.set_context(user_id=123)
        
        await emitter.send_system_notification(db_session, "Test Notification", "success")
        await db_session.flush() # Применяем изменения в сессии
        
        notification = await db_session.get(Notification, 1)
        assert notification is not None
        assert notification.user_id == 123
        assert notification.message == "Test Notification"
        assert notification.level == "success"