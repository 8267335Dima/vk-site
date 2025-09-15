# backend/tests/test_user_endpoints.py
import pytest
from httpx import AsyncClient
from app.db.models import User, DelayProfile, FilterPreset

pytestmark = pytest.mark.asyncio

async def test_get_user_me(async_client: AsyncClient, authorized_user_and_headers: tuple):
    """Проверяет базовый эндпоинт /users/me"""
    _, headers = authorized_user_and_headers
    response = await async_client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "vk_id" in data
    assert data['plan'] == "PRO" # Проверяем, что фикстура правильно установила тариф
    print("\n✓ Эндпоинт /users/me работает корректно.")

async def test_get_user_limits(async_client: AsyncClient, authorized_user_and_headers: tuple):
    """Проверяет эндпоинт с дневными лимитами."""
    _, headers = authorized_user_and_headers
    response = await async_client.get("/api/v1/users/me/limits", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "likes_limit" in data
    assert "friends_add_today" in data
    print("✓ Эндпоинт /users/me/limits работает корректно.")

async def test_update_delay_profile(async_client: AsyncClient, authorized_user_and_headers: tuple):
    """Проверяет смену скорости работы (фича PRO тарифа)."""
    user, headers = authorized_user_and_headers
    
    # 1. Меняем на 'fast'
    response_fast = await async_client.put("/api/v1/users/me/delay-profile", headers=headers, json={"delay_profile": "fast"})
    assert response_fast.status_code == 200
    assert response_fast.json()['delay_profile'] == DelayProfile.fast.value
    print("\n✓ Профиль скорости успешно изменен на 'fast'.")

    # 2. Меняем обратно на 'normal'
    response_normal = await async_client.put("/api/v1/users/me/delay-profile", headers=headers, json={"delay_profile": "normal"})
    assert response_normal.status_code == 200
    assert response_normal.json()['delay_profile'] == DelayProfile.normal.value
    print("✓ Профиль скорости успешно возвращен на 'normal'.")

async def test_filter_presets_lifecycle(async_client: AsyncClient, authorized_user_and_headers: tuple):
    """Тестирует создание, получение и удаление пресета фильтров."""
    _, headers = authorized_user_and_headers
    preset_id = None
    
    try:
        # 1. CREATE
        preset_data = {
            "name": "Тестовый пресет для лайков",
            "action_type": "like_feed",
            "filters": {"sex": 1, "is_online": True}
        }
        resp_create = await async_client.post("/api/v1/users/me/filter-presets", headers=headers, json=preset_data)
        assert resp_create.status_code == 201
        created_preset = resp_create.json()
        preset_id = created_preset['id']
        assert created_preset['name'] == preset_data['name']
        print(f"\n✓ Пресет фильтров успешно создан (ID: {preset_id}).")

        # 2. GET
        resp_get = await async_client.get(f"/api/v1/users/me/filter-presets?action_type=like_feed", headers=headers)
        assert resp_get.status_code == 200
        presets = resp_get.json()
        assert any(p['id'] == preset_id for p in presets)
        print("✓ Созданный пресет присутствует в общем списке.")

    finally:
        # 3. DELETE
        if preset_id:
            resp_del = await async_client.delete(f"/api/v1/users/me/filter-presets/{preset_id}", headers=headers)
            assert resp_del.status_code == 204
            print(f"✓ Пресет (ID: {preset_id}) успешно удален.")