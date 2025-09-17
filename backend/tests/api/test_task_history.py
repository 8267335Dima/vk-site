# tests/api/test_task_history.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.db.models import User, TaskHistory

pytestmark = pytest.mark.anyio

@pytest.fixture
async def failed_task(db_session: AsyncSession, test_user: User) -> TaskHistory:
    """Фикстура для создания неудавшейся задачи в истории."""
    task = TaskHistory(
        user_id=test_user.id,
        # ИСПРАВЛЕНИЕ: Используем точное имя из automations.yml
        task_name="Очистка списка друзей",
        status="FAILURE",
        # ИСПРАВЛЕНИЕ: Структура параметров должна соответствовать Pydantic-модели
        parameters={"count": 100, "filters": {"remove_banned": True}}
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task

@pytest.fixture
async def pending_task(db_session: AsyncSession, test_user: User) -> TaskHistory:
    """Фикстура для создания задачи в очереди."""
    task = TaskHistory(
        user_id=test_user.id,
        task_name="Задача в ожидании",
        status="PENDING",
        arq_job_id="test_job_id_123"
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task

async def test_retry_failed_task(
    async_client: AsyncClient, auth_headers: dict, failed_task: TaskHistory, mocker
):
    """
    Тест успешного повторного запуска задачи, которая ранее завершилась с ошибкой.
    """
    mock_enqueue = mocker.patch('app.api.endpoints.task_history._enqueue_task', return_value={"message": "OK", "task_id": "new_job"})
    
    response = await async_client.post(f"/api/v1/tasks/{failed_task.id}/retry", headers=auth_headers)
    
    assert response.status_code == 200
    mock_enqueue.assert_called_once()


async def test_retry_non_failed_task(
    async_client: AsyncClient, auth_headers: dict, pending_task: TaskHistory
):
    """
    Тест проверяет, что нельзя повторно запустить задачу, которая не имеет статуса FAILURE.
    """
    response = await async_client.post(f"/api/v1/tasks/{pending_task.id}/retry", headers=auth_headers)
    
    assert response.status_code == 400
    assert "Повторить можно только задачу, завершившуюся с ошибкой" in response.json()["detail"]


# ИСПРАВЛЕННЫЙ ТЕСТ
async def test_cancel_pending_task(
    async_client: AsyncClient, auth_headers: dict, pending_task: TaskHistory, db_session: AsyncSession, mock_arq_pool: AsyncMock # <-- Получаем фикстуру
):
    """
    Тест успешной отмены задачи, находящейся в очереди.
    """
    response = await async_client.post(f"/api/v1/tasks/{pending_task.id}/cancel", headers=auth_headers)

    assert response.status_code == 202
    
    await db_session.refresh(pending_task)
    assert pending_task.status == "CANCELLED"
    
    # Теперь эта проверка работает, так как мы проверяем вызов на том же мок-объекте,
    # который был передан в приложение.
    mock_arq_pool.abort_job.assert_awaited_with(pending_task.arq_job_id)


async def test_cancel_completed_task(
    async_client: AsyncClient, auth_headers: dict, failed_task: TaskHistory
):
    """
    Тест проверяет, что нельзя отменить уже завершенную (неудачно) задачу.
    """
    response = await async_client.post(f"/api/v1/tasks/{failed_task.id}/cancel", headers=auth_headers)
    
    assert response.status_code == 400
    assert "Отменить можно только задачи в очереди или в процессе выполнения" in response.json()["detail"]