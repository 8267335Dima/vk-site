# tests/api/test_users.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
# --- ДОБАВЛЕНО: Импортируем AsyncMock ---
from unittest.mock import AsyncMock

from app.db.models import User, DailyStats, FilterPreset
from app.core.enums import PlanName, FeatureKey
from app.db.models.user import ManagedProfile
from app.db.models.payment import Plan
from app.services.vk_api.base import VKAPIError

# Все тесты в этом файле должны использовать anyio
pytestmark = pytest.mark.anyio


async def test_read_users_me_success(async_client: AsyncClient, auth_headers: dict, test_user: User, mocker):
    """
    Тест успешного получения информации о текущем пользователе (/me).
    """
    mock_vk_response = [{
        "id": test_user.vk_id,
        "first_name": "Тестовый",
        "last_name": "Юзер",
        "photo_200": "https://example.com/photo.jpg",
        "status": "Тестовый статус",
        "counters": {"friends": 150}
    }]
    
    # --- НАЧАЛО ИЗМЕНЕНИЯ ---
    # 1. Патчим класс VKAPI там, где он используется (в эндпоинте users)
    mock_vk_api_class = mocker.patch('app.api.endpoints.users.VKAPI')

    # 2. Получаем ссылку на мок-экземпляр, который будет создан при вызове VKAPI()
    mock_instance = mock_vk_api_class.return_value

    # 3. Настраиваем методы на этом мок-экземпляре
    # Метод 'users.get' должен быть асинхронным и возвращать наши данные
    mock_instance.users.get = AsyncMock(return_value=mock_vk_response)
    # Метод 'close' тоже нужно замокать, так как он вызывается в finally
    mock_instance.close = AsyncMock()
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    # Выполняем запрос к нашему API
    response = await async_client.get("/api/v1/users/me", headers=auth_headers)

    # Проверяем результат
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == test_user.id
    assert FeatureKey.PROXY_MANAGEMENT in data["available_features"]
    assert data["first_name"] == "Тестовый"
    assert data["counters"]["friends"] == 150


async def test_get_daily_limits(async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    """
    Тест получения дневных лимитов пользователя (/me/limits).
    """
    today_stats = DailyStats(
        user_id=test_user.id,
        likes_count=25,
        friends_added_count=5
    )
    db_session.add(today_stats)
    await db_session.flush()

    response = await async_client.get("/api/v1/users/me/limits", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["likes_limit"] == test_user.daily_likes_limit
    assert data["likes_today"] == 25
    assert data["friends_add_limit"] == test_user.daily_add_friends_limit
    assert data["friends_add_today"] == 5


async def test_create_and_get_filter_preset(async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    """
    Тест создания и последующего получения пресета фильтров.
    """
    preset_data = {
        "name": "Мои лучшие фильтры",
        "action_type": "remove_friends",
        "filters": {"remove_banned": True, "last_seen_days": 30}
    }

    response_create = await async_client.post("/api/v1/users/me/filter-presets", headers=auth_headers, json=preset_data)

    assert response_create.status_code == 201
    created_data = response_create.json()
    assert created_data["name"] == preset_data["name"]

    response_get = await async_client.get(
        f"/api/v1/users/me/filter-presets?action_type={preset_data['action_type']}",
        headers=auth_headers
    )

    assert response_get.status_code == 200
    presets_list = response_get.json()
    assert len(presets_list) == 1
    assert presets_list[0]["id"] == created_data["id"]

async def test_update_and_get_analytics_settings(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест на успешное обновление и последующее получение
    пользовательских настроек для аналитики.
    """
    # ▼▼▼ ГЛАВНОЕ ИСПРАВЛЕНИЕ ЗДЕСЬ ▼▼▼
    # Arrange: Данные для обновления. Используем ключи из alias Pydantic-модели.
    settings_data = {
        "analytics_settings_posts_count": 77,
        "analytics_settings_photos_count": 177
    }

    # Act: Обновляем настройки
    response_update = await async_client.put(
        "/api/v1/users/me/analytics-settings",
        headers=auth_headers,
        json=settings_data
    )

    # Assert: Проверяем ответ и состояние БД
    assert response_update.status_code == 200
    updated_settings = response_update.json()
    # Pydantic-модель ответа отдает ключи без alias (так как response_model_by_alias=False)
    assert updated_settings["posts_count"] == 77
    assert updated_settings["photos_count"] == 177

    await db_session.refresh(test_user)
    assert test_user.analytics_settings_posts_count == 77
    assert test_user.analytics_settings_photos_count == 177

@pytest.mark.parametrize(
    "payload, expected_status, expected_detail_substring",
    [
        (
            {"name": "", "action_type": "remove_friends", "filters": {}}, 
            422, "String should have at least 1 character"
        ),
        (
            {"name": "a"*51, "action_type": "remove_friends", "filters": {}}, 
            422, "String should have at most 50 characters"
        ),
        (
            {"action_type": "remove_friends", "filters": {}}, 
            422, "Field required"
        ),
    ]
)
async def test_create_filter_preset_validation(
    async_client: AsyncClient, auth_headers: dict, payload, expected_status, expected_detail_substring
):
    """
    Параметризованный тест для проверки ошибок валидации при создании пресета фильтров.
    """
    # Act
    response = await async_client.post(
        "/api/v1/users/me/filter-presets", 
        headers=auth_headers, 
        json=payload
    )

    # Assert
    assert response.status_code == expected_status
    assert expected_detail_substring in str(response.json())

async def test_get_managed_profiles_handles_missing_vk_user(
    async_client: AsyncClient, db_session: AsyncSession, manager_user: User, managed_profile_user: User, get_auth_headers_for, mocker
):
    """
    Тест проверяет, что эндпоинт /me/managed-profiles не падает, если VK API
    не возвращает информацию об одном из управляемых профилей.
    """
    # Arrange:
    # 1. Создаем менеджера и два управляемых профиля в нашей БД.
    
    # ↓↓↓ ИСПРАВЛЕНИЕ ЗДЕСЬ ↓↓↓
    pro_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PRO.name))).scalar_one()
    another_managed_user = User(vk_id=333, encrypted_vk_token="another", plan_id=pro_plan.id)
    # ↑↑↑ КОНЕЦ ИСПРАВЛЕНИЯ ↑↑↑

    db_session.add(another_managed_user)
    await db_session.flush()

    rel1 = ManagedProfile(manager_user_id=manager_user.id, profile_user_id=managed_profile_user.id)
    rel2 = ManagedProfile(manager_user_id=manager_user.id, profile_user_id=another_managed_user.id)
    db_session.add_all([rel1, rel2])
    await db_session.commit()

    # 2. Мокаем VK API так, чтобы он вернул информацию только о менеджере и ПЕРВОМ профиле.
    # Информация о `another_managed_user` (vk_id=333) будет отсутствовать.
    mock_vk_api_class = mocker.patch('app.api.endpoints.users.VKAPI')
    mock_instance = mock_vk_api_class.return_value
    mock_vk_response = [
        {"id": manager_user.vk_id, "first_name": "Manager", "last_name": "User", "photo_50": "url1"},
        {"id": managed_profile_user.vk_id, "first_name": "Managed", "last_name": "Profile", "photo_50": "url2"},
    ]
    mock_instance.users.get = AsyncMock(return_value=mock_vk_response)
    mock_instance.close = AsyncMock()

    # Act:
    manager_headers = get_auth_headers_for(manager_user)
    response = await async_client.get("/api/v1/users/me/managed-profiles", headers=manager_headers)

    # Assert:
    assert response.status_code == 200
    data = response.json()
    
    # Ответ должен содержать всех трех пользователей (менеджер + 2 профиля) из нашей БД
    assert len(data) == 3 
    
    profiles_by_v_id = {p['vk_id']: p for p in data}
    
    # Проверяем, что данные для существующих в VK пользователей подтянулись
    assert profiles_by_v_id[manager_user.vk_id]['first_name'] == "Manager"
    assert profiles_by_v_id[managed_profile_user.vk_id]['first_name'] == "Managed"

    # Ключевая проверка: для "пропавшего" пользователя подставились значения по умолчанию
    assert profiles_by_v_id[another_managed_user.vk_id]['first_name'] == "N/A"
    assert profiles_by_v_id[another_managed_user.vk_id]['last_name'] == ""

async def test_create_duplicate_filter_preset_fails(
    async_client: AsyncClient, auth_headers: dict, test_user: User
):
    """
    Тест проверяет, что API вернет ошибку 409 Conflict при попытке создать
    пресет фильтров с именем, которое уже существует для того же действия.
    """
    preset_data = {
        "name": "Удаление неактивных",
        "action_type": "remove_friends",
        "filters": {"last_seen_days": 90}
    }

    # 1. Создаем пресет в первый раз - должно быть успешно
    response_first = await async_client.post(
        "/api/v1/users/me/filter-presets",
        headers=auth_headers,
        json=preset_data
    )
    assert response_first.status_code == 201

    # 2. Пытаемся создать пресет с тем же именем и типом действия во второй раз
    response_second = await async_client.post(
        "/api/v1/users/me/filter-presets",
        headers=auth_headers,
        json=preset_data
    )

    # Assert: Ожидаем ошибку 409 Conflict
    assert response_second.status_code == 409
    assert "Пресет с таким названием для данного действия уже существует" in response_second.json()["detail"]

async def test_read_users_me_vk_api_error(async_client: AsyncClient, auth_headers: dict, test_user: User, mocker):
    """
    Тест проверяет, что эндпоинт /me возвращает корректную ошибку 424,
    если VK API недоступен или токен невалиден.
    """
    # Arrange
    # Мокаем VK API так, чтобы он выбрасывал исключение
    mock_vk_api_class = mocker.patch('app.api.endpoints.users.VKAPI')
    mock_instance = mock_vk_api_class.return_value
    mock_instance.users.get.side_effect = VKAPIError("Invalid token", 5)
    mock_instance.close = AsyncMock()
    
    # Act
    response = await async_client.get("/api/v1/users/me", headers=auth_headers)
    
    # Assert
    assert response.status_code == 424 # Failed Dependency
    assert "Ошибка VK API: Invalid token" in response.json()["detail"]

@pytest.mark.parametrize(
    "payload, expected_status, expected_detail",
    [
        # Невалидное значение для posts_count (меньше 10)
        ({"analytics_settings_posts_count": 5, "analytics_settings_photos_count": 200}, 422, "Input should be greater than or equal to 10"),
        # Невалидное значение для posts_count (больше 500)
        ({"analytics_settings_posts_count": 501, "analytics_settings_photos_count": 200}, 422, "Input should be less than or equal to 500"),
        # Невалидное значение для photos_count (меньше 10)
        ({"analytics_settings_posts_count": 100, "analytics_settings_photos_count": 9}, 422, "Input should be greater than or equal to 10"),
        # Невалидное значение для photos_count (больше 1000)
        ({"analytics_settings_posts_count": 100, "analytics_settings_photos_count": 1001}, 422, "Input should be less than or equal to 1000"),
    ]
)
async def test_update_analytics_settings_validation(
    async_client: AsyncClient, auth_headers: dict, payload, expected_status, expected_detail
):
    """Проверяет Pydantic-валидацию для эндпоинта настроек аналитики."""
    response = await async_client.put(
        "/api/v1/users/me/analytics-settings", headers=auth_headers, json=payload
    )
    assert response.status_code == expected_status
    assert expected_detail in str(response.json())