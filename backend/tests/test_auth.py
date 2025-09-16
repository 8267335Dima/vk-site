# backend/tests/test_auth.py
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import random

from app.db.models import User, ManagedProfile
from app.core.config import settings
from app.core.security import create_access_token, encrypt_data

@pytest.fixture
async def managed_user_setup(db_session: AsyncSession, authorized_user_and_headers):
    """
    Фикстура, которая создает в БД менеджера и фейковый управляемый профиль.
    Для этого профиля используется корректно зашифрованный, но невалидный для VK токен.
    """
    manager_user, _ = authorized_user_and_headers

    async with db_session.begin_nested():
        # Шифруем фейковый токен, чтобы проверка decrypt_data прошла успешно
        encrypted_fake_token = encrypt_data("this_is_a_valid_fake_vk_token")
        
        managed_user = User(
            vk_id=random.randint(1000000000, 2000000000), 
            encrypted_vk_token=encrypted_fake_token
        )
        db_session.add(managed_user)
        await db_session.flush()

        link = ManagedProfile(manager_user_id=manager_user.id, profile_user_id=managed_user.id)
        db_session.add(link)
        
    await db_session.refresh(manager_user, attribute_names=["managed_profiles"])
    
    print(f"\n[SETUP] Создан временный управляемый профиль (ID: {managed_user.id}) для менеджера (ID: {manager_user.id})")
    
    yield manager_user, managed_user
    
    print("[CLEANUP] Rollback by db_session fixture will clean up created test data.")


async def test_login_valid_token(async_client: AsyncClient):
    """
    Этот тест остается "строго реальным". Он проверяет логин с настоящим токеном.
    """
    test_token = settings.VK_HEALTH_CHECK_TOKEN
    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": test_token})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data['manager_id'] == data['active_profile_id']


async def test_login_invalid_token(async_client: AsyncClient):
    """
    Этот тест проверяет обработку невалидного токена.
    """
    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": "invalid_token"})
    assert response.status_code == 401


async def test_switch_profile(async_client: AsyncClient, managed_user_setup, monkeypatch):
    """
    Этот тест проверяет логику переключения. Он использует МОК для запроса к VK API,
    потому что управляемый пользователь - фейковый.
    """
    manager, managed = managed_user_setup
    
    # 1. Создаем "мок" - поддельную функцию, которая будет заменять реальный метод API.
    #    Она просто возвращает словарь, имитирующий успешный ответ от ВКонтакте.
    async def mock_users_get(*args, **kwargs):
        # Важно, чтобы vk_id в ответе совпадал с vk_id нашего тестового пользователя
        return [{
            "id": managed.vk_id,
            "first_name": "Managed",
            "last_name": "TestUser",
            "photo_200": "fake_photo_url.jpg",
            "status": "Testing...",
            "counters": {"friends": 50}
        }]

    # 2. Используем monkeypatch, чтобы подменить реальный метод API нашим моком.
    #    Когда код приложения вызовет `vk_api.users.get`, вместо реального запроса
    #    сработает наша функция `mock_users_get`.
    monkeypatch.setattr("app.services.vk_api.users.UsersAPI.get", mock_users_get)

    # --- Остальная часть теста выполняется как обычно ---
    manager_token = create_access_token(data={"sub": str(manager.id), "profile_id": str(manager.id)})
    manager_headers = {"Authorization": f"Bearer {manager_token}"}
    
    print(f"[ACTION] Переключение на профиль ID: {managed.id}")
    response = await async_client.post("/api/v1/auth/switch-profile", headers=manager_headers, json={"profile_id": managed.id})
    assert response.status_code == 200
    
    switched_data = response.json()
    assert switched_data['active_profile_id'] == managed.id
    
    switched_headers = {"Authorization": f"Bearer {switched_data['access_token']}"}
    
    # Этот вызов теперь не пойдет в интернет, а вызовет `mock_users_get`
    response_me = await async_client.get("/api/v1/users/me", headers=switched_headers)

    # 3. Проверка пройдет, так как наш мок вернет успешный результат.
    assert response_me.status_code == 200
    assert response_me.json()['vk_id'] == managed.vk_id

    print("[SUCCESS] Проверка /users/me после переключения прошла успешно.")

    print(f"[ACTION] Переключение обратно на профиль менеджера ID: {manager.id}")
    response_back = await async_client.post("/api/v1/auth/switch-profile", headers=manager_headers, json={"profile_id": manager.id})
    assert response_back.status_code == 200
    assert response_back.json()['active_profile_id'] == manager.id