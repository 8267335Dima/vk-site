# backend/tests/test_auth.py (Полная обновленная версия)
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from app.db.models import User, ManagedProfile
from app.core.config import settings
from app.core.security import create_access_token
import random

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def managed_user_setup(db_session: AsyncSession, authorized_user_and_headers):
    """Создает временного 'управляемого' пользователя для теста переключения."""
    manager_user, _ = authorized_user_and_headers
    
    # Создаем фейкового пользователя в БД
    managed_user = User(
        vk_id=random.randint(1000000000, 2000000000), # Уникальный VK ID
        encrypted_vk_token="fake_token"
    )
    db_session.add(managed_user)
    await db_session.flush()

    # Создаем связь "менеджер -> управляемый"
    managed_profile_link = ManagedProfile(
        manager_user_id=manager_user.id,
        profile_user_id=managed_user.id
    )
    db_session.add(managed_profile_link)
    await db_session.commit()
    
    print(f"\n[SETUP] Создан временный управляемый профиль (ID: {managed_user.id}) для менеджера (ID: {manager_user.id})")

    yield manager_user, managed_user

    # Очистка после теста
    print("[CLEANUP] Удаление временного управляемого профиля...")
    await db_session.execute(delete(ManagedProfile).where(ManagedProfile.id == managed_profile_link.id))
    await db_session.execute(delete(User).where(User.id == managed_user.id))
    await db_session.commit()


async def test_login_valid_token(async_client: AsyncClient):
    """Тест успешного входа с валидным токеном."""
    test_token = settings.VK_HEALTH_CHECK_TOKEN
    assert test_token, "Переменная VK_HEALTH_CHECK_TOKEN должна быть в .env"

    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": test_token})
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data['manager_id'] == data['active_profile_id'] # При первом входе ID должны совпадать

async def test_login_invalid_token(async_client: AsyncClient):
    """Тест входа с невалидным токеном."""
    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": "invalid_token"})
    assert response.status_code == 401

async def test_access_protected_route(async_client: AsyncClient, authorized_user_and_headers):
    """Проверяет доступ к защищенному эндпоинту (/users/me) с валидным токеном."""
    _, headers = authorized_user_and_headers
    response = await async_client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    assert "vk_id" in response.json()

async def test_switch_profile(async_client: AsyncClient, managed_user_setup):
    """Тестирует переключение на управляемый профиль и обратно."""
    manager, managed = managed_user_setup
    
    # 1. Генерируем токен для менеджера
    manager_token = create_access_token(data={"sub": str(manager.id), "profile_id": str(manager.id)})
    manager_headers = {"Authorization": f"Bearer {manager_token}"}
    
    # 2. Переключаемся на управляемый профиль
    print(f"[ACTION] Переключение на профиль ID: {managed.id}")
    response = await async_client.post("/api/v1/auth/switch-profile", headers=manager_headers, json={"profile_id": managed.id})
    assert response.status_code == 200
    switched_data = response.json()
    assert switched_data['manager_id'] == manager.id
    assert switched_data['active_profile_id'] == managed.id
    print("[VERIFY] ✓ Успешно переключились. active_profile_id изменен.")

    # 3. Проверяем, что с новым токеном мы видим данные управляемого профиля
    switched_headers = {"Authorization": f"Bearer {switched_data['access_token']}"}
    response_me = await async_client.get("/api/v1/users/me", headers=switched_headers)
    assert response_me.status_code == 200
    # Проверяем, что /me возвращает VK ID управляемого, а не менеджера
    assert response_me.json()['vk_id'] == managed.vk_id
    print("[VERIFY] ✓ Эндпоинт /me с новым токеном возвращает данные управляемого профиля.")

    # 4. Переключаемся обратно на свой профиль
    print(f"[ACTION] Переключение обратно на профиль менеджера ID: {manager.id}")
    response_back = await async_client.post("/api/v1/auth/switch-profile", headers=manager_headers, json={"profile_id": manager.id})
    assert response_back.status_code == 200
    back_data = response_back.json()
    assert back_data['active_profile_id'] == manager.id
    print("[VERIFY] ✓ Успешно переключились обратно.")