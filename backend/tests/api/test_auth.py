# tests/api/test_auth.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from unittest.mock import MagicMock
from fastapi import HTTPException
from httpx import AsyncClient
# Импортируем саму функцию эндпоинта и Pydantic-модель для запроса
from app.api.endpoints.auth import login_via_vk, TokenRequest
from app.db.models import User, LoginHistory

pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_request() -> MagicMock:
    """Фикстура для создания мока объекта Request."""
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers.get.return_value = "Test User Agent"
    return request


async def test_login_via_vk_new_user_logic(
    db_session: AsyncSession, mock_request: MagicMock, mocker
):
    """
    Тест логики успешного логина и создания нового пользователя.
    Мы вызываем функцию эндпоинта напрямую, а не через HTTP.
    """
    # Arrange
    # 1. Мокаем внешнюю зависимость, которая ходит в интернет
    mocker.patch('app.api.endpoints.auth.is_token_valid', return_value=987654)
    # 2. Создаем Pydantic-модель с данными запроса
    token_req = TokenRequest(vk_token="valid_new_user_token")

    # Act
    # 3. Вызываем функцию эндпоинта напрямую, передавая все зависимости
    response_model = await login_via_vk(
        request=mock_request,
        db=db_session,
        token_request=token_req
    )

    # Assert
    # 4. Проверяем, что вернулся правильный Pydantic-объект
    assert "access_token" in response_model.model_dump()
    assert response_model.token_type == "bearer"
    assert response_model.manager_id is not None

    # 5. Проверяем, что пользователь и история входа были созданы в БД
    user_in_db = (await db_session.execute(
        select(User).where(User.vk_id == 987654)
    )).scalar_one()
    login_history_in_db = (await db_session.execute(
        select(LoginHistory).where(LoginHistory.user_id == user_in_db.id)
    )).scalar_one()

    assert user_in_db is not None
    assert login_history_in_db is not None
    assert login_history_in_db.ip_address == "127.0.0.1"


async def test_login_via_vk_existing_user_logic(
    db_session: AsyncSession, test_user: User, mock_request: MagicMock, mocker
):
    """Тест логики успешного логина для уже существующего пользователя."""
    # Arrange
    mocker.patch('app.api.endpoints.auth.is_token_valid', return_value=test_user.vk_id)
    token_req = TokenRequest(vk_token="valid_existing_user_token")

    # Act
    response_model = await login_via_vk(
        request=mock_request,
        db=db_session,
        token_request=token_req
    )

    # Assert
    assert response_model.manager_id == test_user.id
    assert response_model.active_profile_id == test_user.id


async def test_login_via_vk_invalid_token_logic(
    db_session: AsyncSession, mock_request: MagicMock, mocker
):
    """
    Тест на ошибку при невалидном VK токене.
    Проверяем, что функция выбрасывает HTTPException.
    """
    # Arrange
    mocker.patch('app.api.endpoints.auth.is_token_valid', return_value=None)
    token_req = TokenRequest(vk_token="invalid_token")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await login_via_vk(
            request=mock_request,
            db=db_session,
            token_request=token_req
        )

    # Проверяем детали исключения
    assert exc_info.value.status_code == 401
    assert "Неверный или просроченный токен VK" in exc_info.value.detail

async def test_switch_to_unmanaged_profile_fails(
    async_client: AsyncClient, 
    db_session: AsyncSession, 
    manager_user: User, 
    team_member_user: User, # Просто как пользователь, которым не управляют
    get_auth_headers_for
):
    """
    Тест безопасности: менеджер не может переключиться на профиль пользователя,
    который не находится у него в управлении.
    """
    # Arrange
    # Убедимся, что team_member_user НЕ является управляемым профилем для manager_user
    manager_headers = get_auth_headers_for(manager_user)
    
    # Act
    response = await async_client.post(
        "/api/v1/auth/switch-profile",
        headers=manager_headers,
        json={"profile_id": team_member_user.id}
    )
    
    # Assert
    assert response.status_code == 403
    assert "Доступ к этому профилю запрещен" in response.json()["detail"]