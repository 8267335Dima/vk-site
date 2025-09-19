# tests/api/test_groups.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.db.models import User, Group

pytestmark = pytest.mark.anyio

@pytest.fixture
def mock_group_identity_service(mocker):
    """Мокает сервис проверки токена группы."""
    mock_service = mocker.patch("app.api.endpoints.groups.GroupIdentityService.get_group_info_by_token")
    mock_service.return_value = {
        "vk_group_id": 12345,
        "name": "Тестовая группа",
        "photo_100": "http://example.com/pic.jpg"
    }
    return mock_service

async def test_add_managed_group_success(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
    mock_group_identity_service: AsyncMock
):
    """Тест успешного добавления управляемого сообщества."""
    request_data = {"vk_group_id": 12345, "access_token": "valid_group_token"}
    
    response = await async_client.post("/api/v1/groups", headers=auth_headers, json=request_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Тестовая группа"

    group_in_db = await db_session.get(Group, data["id"])
    assert group_in_db is not None
    assert group_in_db.admin_user_id == test_user.id

async def test_add_managed_group_invalid_token(
    async_client: AsyncClient,
    auth_headers: dict,
    mocker
):
    """Тест ошибки при добавлении группы с невалидным токеном."""
    mocker.patch(
        "app.api.endpoints.groups.GroupIdentityService.get_group_info_by_token",
        return_value=None # Сервис говорит, что токен плохой
    )
    request_data = {"vk_group_id": 54321, "access_token": "invalid_token"}

    response = await async_client.post("/api/v1/groups", headers=auth_headers, json=request_data)

    assert response.status_code == 400
    assert "Неверный токен" in response.json()["detail"]