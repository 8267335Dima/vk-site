# tests/api/test_middleware.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User

pytestmark = pytest.mark.anyio

# Используем параметризацию для проверки всех "плохих" статусов
@pytest.mark.parametrize(
    "user_status, expected_code, expected_detail",
    [
        ({"is_deleted": True}, 403, "Аккаунт был удален."),
        ({"is_frozen": True}, 403, "Ваш аккаунт временно заморожен администратором."),
    ]
)
async def test_user_status_middleware_blocks_access(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    get_auth_headers_for, # Используем фикстуру-фабрику
    user_status: dict,
    expected_code: int,
    expected_detail: str
):
    """
    Тест проверяет, что middleware в main.py блокирует запросы
    от замороженных и удаленных пользователей.
    """
    # Arrange: Устанавливаем пользователю "плохой" статус
    for key, value in user_status.items():
        setattr(test_user, key, value)
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Генерируем заголовки для этого конкретного пользователя
    headers = get_auth_headers_for(test_user)

    # Act: Пытаемся получить доступ к любому защищенному эндпоинту
    response = await async_client.get("/api/v1/users/me/limits", headers=headers)

    # Assert
    assert response.status_code == expected_code
    assert response.json()["detail"] == expected_detail

async def test_user_status_middleware_allows_active_user(
    async_client: AsyncClient, auth_headers: dict
):
    """Тест проверяет, что middleware пропускает активных пользователей."""
    # Arrange (пользователь из auth_headers активен по умолчанию)
    
    # Act
    response = await async_client.get("/api/v1/users/me/limits", headers=auth_headers)

    # Assert
    assert response.status_code == 200