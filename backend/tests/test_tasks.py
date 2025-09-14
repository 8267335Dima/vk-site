# backend/tests/test_tasks.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import TaskHistory, User
from .test_scenarios import login_and_headers # Используем хелпер из другого теста

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def test_user(db_session: AsyncSession):
    # Находим тестового пользователя в БД (созданного тестом авторизации)
    user = await db_session.scalar(select(User).where(User.vk_id == 850946882))
    assert user is not None
    return user

async def test_run_like_feed_task(async_client: AsyncClient, db_session: AsyncSession, test_user: User):
    """
    Тест запускает задачу "Лайки в ленте" и проверяет,
    что в БД была создана соответствующая запись TaskHistory.
    """
    headers = await login_and_headers(async_client)
    
    task_payload = {
        "count": 25,
        "filters": {"only_with_photo": True}
    }
    
    # 1. Выполняем запрос на запуск задачи
    response = await async_client.post(
        "/api/v1/tasks/run/like_feed", 
        headers=headers, 
        json=task_payload
    )
    
    # 2. Проверяем успешный ответ
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "success"
    assert "task_id" in response_data
    
    # 3. Проверяем, что в БД появилась запись о задаче
    # (Это доказывает, что запрос дошел до логики и был обработан)
    await db_session.commit() # Сохраняем изменения, сделанные эндпоинтом
    
    task_history_entry = await db_session.scalar(
        select(TaskHistory).where(
            TaskHistory.user_id == test_user.id,
            TaskHistory.celery_task_id == response_data["task_id"]
        )
    )
    
    assert task_history_entry is not None
    assert task_history_entry.task_name == "Лайки в ленте новостей"
    assert task_history_entry.status == "PENDING"
    assert task_history_entry.parameters["count"] == 25
    assert task_history_entry.parameters["filters"]["only_with_photo"] is True