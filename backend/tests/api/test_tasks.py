# --- START OF FILE tests/api/test_tasks.py ---

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock
from app.db.models import DailyStats
from app.db.models import User, TaskHistory
from app.core.enums import PlanName, TaskKey
from app.tasks.logic.maintenance_jobs import _check_expired_plans_async
from app.db.models.payment import Plan

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

async def test_run_task_permission_denied(
    async_client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
    get_auth_headers_for # Используем новую фикстуру
):
    # Arrange: Переводим пользователя на базовый тариф
    base_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.BASE.name))).scalar_one()
    test_user.plan_id = base_plan.id
    await db_session.commit()
    await db_session.refresh(test_user, ['plan'])
    
    # Генерируем токен ПОСЛЕ изменения пользователя
    headers = get_auth_headers_for(test_user)

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
    # ... (логика теста без изменений до генерации токена)
    expired_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.EXPIRED.name))).scalar_one()
    pro_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PRO.name))).scalar_one()
    
    test_user.plan_id = pro_plan.id
    test_user.plan_expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()
    await db_session.refresh(test_user)

    await _check_expired_plans_async(session=db_session)
    await db_session.refresh(test_user, ['plan'])
    
    assert test_user.plan.name_id == PlanName.EXPIRED.name
    
    # Генерируем токен для пользователя с уже истекшим тарифом
    headers = get_auth_headers_for(test_user)
    task_key = TaskKey.LIKE_FEED
    task_params = {"count": 10, "filters": {}}

    # Act
    response = await async_client.post(f"/api/v1/tasks/run/{task_key.value}", headers=headers, json=task_params)
    
    # Assert
    assert response.status_code == 403
    assert "Действие недоступно на вашем тарифе" in response.json()["detail"]

@pytest.mark.parametrize("task_key, daily_limit_field, stat_field, used_today, expected_max_val", [
    # Лайки: лимит 100, использовано 30 -> можно еще 70
    (TaskKey.LIKE_FEED, "daily_likes_limit", "likes_count", 30, 70),
    # Добавление друзей: лимит 40, использовано 0 -> можно 40
    (TaskKey.ADD_RECOMMENDED, "daily_add_friends_limit", "friends_added_count", 0, 40),
    # Сообщения: лимит 50, использовано 50 -> можно 0
    (TaskKey.MASS_MESSAGING, "daily_message_limit", "messages_sent_count", 50, 0),
    # Удаление друзей (использует тот же лимит, что и выход из групп в конфиге)
    (TaskKey.REMOVE_FRIENDS, "daily_leave_groups_limit", "friends_removed_count", 10, 190),
])
async def test_get_task_config_calculates_remaining_limit(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession,
    task_key, daily_limit_field, stat_field, used_today, expected_max_val
):
    """
    Тест проверяет, что эндпоинт /config правильно рассчитывает
    максимальное доступное значение для слайдера на основе дневных лимитов и текущего использования.
    """
    # Arrange
    # Устанавливаем лимиты и сегодняшнее использование в БД
    setattr(test_user, daily_limit_field, used_today + expected_max_val)
    stats = DailyStats(user_id=test_user.id)
    setattr(stats, stat_field, used_today)
    db_session.add_all([test_user, stats])
    await db_session.commit()

    # Act
    response = await async_client.get(f"/api/v1/tasks/{task_key.value}/config", headers=auth_headers)

    # Assert
    assert response.status_code == 200
    data = response.json()
    slider_field = next((field for field in data["fields"] if field["name"] == "count"), None)
    
    assert slider_field is not None
    assert slider_field["max_value"] == expected_max_val