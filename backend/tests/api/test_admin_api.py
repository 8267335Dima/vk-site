# tests/api/test_admin_api.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.db.models import User, TaskHistory

pytestmark = pytest.mark.anyio

async def test_get_performance_data(
    async_client: AsyncClient, 
    db_session: AsyncSession, 
    admin_user: User, 
    get_auth_headers_for
):
    """
    Тест проверяет эндпоинт сбора статистики производительности задач.
    Создаются задачи с разными статусами и длительностью для проверки
    правильности агрегации данных.
    """
    # Arrange: Создаем историю задач для анализа
    now = datetime.utcnow()
    # Задача 1: Успешная, длилась 10 секунд
    task1_success = TaskHistory(
        user_id=admin_user.id, task_name="Лайки в ленте", status="SUCCESS", 
        started_at=now, finished_at=now + timedelta(seconds=10)
    )
    # Задача 2: Успешная, длилась 20 секунд
    task2_success = TaskHistory(
        user_id=admin_user.id, task_name="Лайки в ленте", status="SUCCESS", 
        started_at=now, finished_at=now + timedelta(seconds=20)
    )
    # Задача 3: Проваленная
    task3_failure = TaskHistory(
        user_id=admin_user.id, task_name="Лайки в ленте", status="FAILURE"
    )
    # Задача 4: Другого типа, для проверки группировки
    task4_other = TaskHistory(
        user_id=admin_user.id, task_name="Массовая рассылка", status="SUCCESS",
        started_at=now, finished_at=now + timedelta(seconds=5)
    )
    # Задача 5: Успешная, но без времени выполнения (не должна учитываться в avg_duration)
    task5_no_time = TaskHistory(
        user_id=admin_user.id, task_name="Лайки в ленте", status="SUCCESS"
    )
    db_session.add_all([task1_success, task2_success, task3_failure, task4_other, task5_no_time])
    await db_session.commit()

    admin_headers = get_auth_headers_for(admin_user)

    # Act
    response = await async_client.get("/api/v1/admin/dashboard/performance", headers=admin_headers)

    # Assert
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Преобразуем список в словарь для удобства проверки
    performance_map = {item["task_name"]: item for item in data}
    
    # Проверяем агрегацию для задачи "Лайки в ленте"
    likes_task_stats = performance_map.get("Лайки в ленте")
    assert likes_task_stats is not None
    assert likes_task_stats["total_runs"] == 4  # 3 успеха + 1 провал
    # 1 провал из 4 запусков = 25%
    assert likes_task_stats["failure_rate"] == 25.0
    # Среднее от 10 и 20 секунд = 15.0
    assert likes_task_stats["avg_duration"] == pytest.approx(15.0)

    # Проверяем агрегацию для "Массовой рассылки"
    messaging_task_stats = performance_map.get("Массовая рассылка")
    assert messaging_task_stats is not None
    assert messaging_task_stats["total_runs"] == 1
    assert messaging_task_stats["failure_rate"] == 0.0
    assert messaging_task_stats["avg_duration"] == pytest.approx(5.0)