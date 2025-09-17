# tests/api/test_notifications.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, Notification

pytestmark = pytest.mark.anyio


async def test_get_notifications(async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    """
    Тест на получение списка уведомлений и количества непрочитанных.
    """
    # Arrange: Создаем 3 уведомления, 2 из них непрочитанные
    n1 = Notification(user_id=test_user.id, message="Первое", level="info", is_read=True)
    n2 = Notification(user_id=test_user.id, message="Второе", level="success", is_read=False)
    n3 = Notification(user_id=test_user.id, message="Третье", level="error", is_read=False)
    db_session.add_all([n1, n2, n3])
    await db_session.commit()

    # Act
    response = await async_client.get("/api/v1/notifications", headers=auth_headers)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["unread_count"] == 2
    assert len(data["items"]) == 3
    assert data["items"][0]["message"] == "Третье" # Проверяем сортировку по дате (новые вверху)


async def test_mark_notifications_as_read(async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    """
    Тест на пометку всех уведомлений пользователя как прочитанных.
    """
    # Arrange: Создаем 2 непрочитанных уведомления
    n1 = Notification(user_id=test_user.id, message="Непрочитанное 1", is_read=False)
    n2 = Notification(user_id=test_user.id, message="Непрочитанное 2", is_read=False)
    db_session.add_all([n1, n2])
    await db_session.commit()

    # Act
    response = await async_client.post("/api/v1/notifications/read", headers=auth_headers)

    # Assert
    assert response.status_code == 204 # No Content

    # Проверяем, что в БД все уведомления теперь прочитаны
    stmt = select(Notification).where(Notification.user_id == test_user.id)
    result = await db_session.execute(stmt)
    notifications_in_db = result.scalars().all()
    assert all(n.is_read for n in notifications_in_db)