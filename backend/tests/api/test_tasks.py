# --- START OF FILE tests/api/test_tasks.py ---

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock

from app.db.models import User, TaskHistory
from app.core.constants import PlanName, TaskKey
from app.tasks.logic.maintenance_jobs import _check_expired_plans_async

pytestmark = pytest.mark.anyio


async def test_run_task_success(
    async_client: AsyncClient, auth_headers: dict, mock_arq_pool: AsyncMock, test_user: User, db_session: AsyncSession
):
    """
    Тест успешного запуска задачи.
    """
    task_key = TaskKey.LIKE_FEED
    task_params = {"count": 25, "filters": {}}

    response = await async_client.post(f"/api/v1/tasks/run/{task_key.value}", headers=auth_headers, json=task_params)

    assert response.status_code == 200
    data = response.json()
    assert "Задача 'Лайки в ленте новостей' успешно добавлена в очередь." in data["message"]
    mock_arq_pool.enqueue_job.assert_called_once()
    history_entry = (await db_session.execute(
        select(TaskHistory).where(TaskHistory.user_id == test_user.id)
    )).scalar_one()
    assert history_entry is not None
    assert history_entry.status == "PENDING"
    assert history_entry.parameters["count"] == 25


async def test_run_task_with_defer(
    async_client: AsyncClient, auth_headers: dict, mock_arq_pool: AsyncMock
):
    """
    Тест запуска отложенной задачи с параметром 'publish_at'.
    """
    task_key = TaskKey.ADD_RECOMMENDED
    publish_time = datetime.now(UTC) + timedelta(hours=1)
    task_params = {"count": 10, "filters": {}, "publish_at": publish_time.isoformat()}
    
    response = await async_client.post(f"/api/v1/tasks/run/{task_key.value}", headers=auth_headers, json=task_params)
    
    assert response.status_code == 200
    
    mock_arq_pool.enqueue_job.assert_called_once()
    _, call_kwargs = mock_arq_pool.enqueue_job.call_args
    assert "_defer_until" in call_kwargs
    
    deferred_time = call_kwargs["_defer_until"]
    assert isinstance(deferred_time, datetime)
    assert abs((deferred_time - publish_time).total_seconds()) < 1

# ИСПРАВЛЕННЫЙ ТЕСТ
async def test_run_task_permission_denied(
    async_client: AsyncClient, 
    test_user: User, 
    db_session: AsyncSession,
    get_auth_headers_for # Используем фикстуру-фабрику
):
    """
    Тест на ошибку при попытке запустить задачу, недоступную по тарифу.
    """
    # Arrange: Переводим пользователя на базовый тариф
    test_user.plan = PlanName.BASE.name
    await db_session.commit()
    await db_session.refresh(test_user)
    
    # --- ИСПРАВЛЕНИЕ: Генерируем токен ПОСЛЕ изменения пользователя ---
    headers = get_auth_headers_for(test_user)

    # `birthday_congratulation` недоступна на BASE
    task_key = TaskKey.BIRTHDAY_CONGRATULATION
    task_params = {}

    # Act
    response = await async_client.post(f"/api/v1/tasks/run/{task_key.value}", headers=headers, json=task_params)

    # Assert
    assert response.status_code == 403
    assert "недоступно на вашем тарифе" in response.json()["detail"]


async def test_preview_task_audience(
    async_client: AsyncClient, auth_headers: dict, mocker
):
    task_key = TaskKey.MASS_MESSAGING
    preview_params = {
        "count": 50,
        "message_text": "dummy text for validation",
        "filters": {"sex": 1}
    }
    mocker.patch(
        "app.services.message_service.MessageService.get_mass_messaging_targets",
        return_value=[{"id": 1}, {"id": 2}, {"id": 3}]
    )
    mocker.patch("app.services.vk_api.VKAPI.close")
    response = await async_client.post(f"/api/v1/tasks/preview/{task_key.value}", headers=auth_headers, json=preview_params)
    assert response.status_code == 200
    assert response.json() == {"found_count": 3}

async def test_run_task_with_expired_plan(
    async_client: AsyncClient, test_user: User, db_session: AsyncSession, get_auth_headers_for
):
    """
    Тест: Пользователь с истекшим тарифом получает ошибку при попытке запустить любую задачу.
    """
    # Arrange:
    # 1. Устанавливаем пользователю PRO тариф, который истек вчера.
    test_user.plan = PlanName.PRO.name
    test_user.plan_expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()
    await db_session.refresh(test_user)

    # 2. Запускаем логику cron-задачи, чтобы она "отключила" тариф пользователя.
    await _check_expired_plans_async(session_for_test=db_session)
    await db_session.refresh(test_user)
    
    # Убедимся, что тариф действительно сменился на Expired
    assert test_user.plan == "Expired"
    
    # 3. Генерируем токен для пользователя с уже истекшим тарифом.
    headers = get_auth_headers_for(test_user)
    task_key = TaskKey.LIKE_FEED
    task_params = {"count": 10, "filters": {}}

    # Act: Пытаемся запустить задачу
    response = await async_client.post(f"/api/v1/tasks/run/{task_key.value}", headers=headers, json=task_params)
    
    # Assert: Ожидаем ошибку 403 Forbidden
    assert response.status_code == 403
    assert "Действие недоступно на вашем тарифе 'Expired'" in response.json()["detail"]