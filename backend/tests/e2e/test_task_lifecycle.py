# tests/e2e/test_task_lifecycle.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.db.models import User, TaskHistory
from app.core.constants import TaskKey

pytestmark = pytest.mark.anyio

async def test_task_cancellation_e2e(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
    mock_arq_pool: AsyncMock # Используем мок ARQ из conftest
):
    """
    E2E Тест:
    1. Пользователь создает задачу через API.
    2. Пользователь отменяет эту задачу через API.
    3. Проверяем, что ARQ получил команду на отмену.
    4. Проверяем, что API истории задач показывает статус CANCELLED.
    """
    # Arrange & Act (Phase 1): Создаем задачу
    task_key = TaskKey.LIKE_FEED
    task_params = {"count": 100, "filters": {}}
    response_run = await async_client.post(
        f"/api/v1/tasks/run/{task_key.value}",
        headers=auth_headers,
        json=task_params
    )
    assert response_run.status_code == 200
    
    # Получаем ID созданной задачи из БД
    task_in_db = await db_session.get(TaskHistory, 1)
    assert task_in_db is not None
    assert task_in_db.status == "PENDING"
    
    task_history_id = task_in_db.id
    arq_job_id = task_in_db.arq_job_id

    # Act (Phase 2): Отменяем задачу
    response_cancel = await async_client.post(
        f"/api/v1/tasks/{task_history_id}/cancel",
        headers=auth_headers
    )
    assert response_cancel.status_code == 202

    # Assert (Phase 1): Проверяем взаимодействие с ARQ
    mock_arq_pool.abort_job.assert_awaited_with(arq_job_id)

    # Act (Phase 3): Запрашиваем историю задач
    response_history = await async_client.get(
        "/api/v1/tasks/history",
        headers=auth_headers
    )
    assert response_history.status_code == 200

    # Assert (Phase 2): Проверяем ответ от API истории
    history_data = response_history.json()
    assert history_data["total"] == 1
    cancelled_task = history_data["items"][0]
    assert cancelled_task["id"] == task_history_id
    assert cancelled_task["status"] == "CANCELLED"
    assert "Задача отменена пользователем" in cancelled_task["result"]