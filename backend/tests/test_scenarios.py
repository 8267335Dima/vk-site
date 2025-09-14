import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# Данные для нового сценария
SCENARIO_PAYLOAD = {
    "name": "Тестовый сценарий",
    "schedule": "0 10 * * 1-5",
    "is_active": True,
    "nodes": [
        {
            "id": "start",
            "type": "start",
            "position": {"x": 250, "y": 25},
            "data": {"id": "start", "type": "start"}
        }
    ],
    "edges": []
}

@pytest.fixture(scope="module")
async def authenticated_user_a(async_client: AsyncClient, monkeypatch) -> dict:
    """Фикстура для создания и аутентификации первого пользователя (User A)."""
    async def mock_is_token_valid(token):
        return 900000001
    monkeypatch.setattr("app.api.endpoints.auth.is_token_valid", mock_is_token_valid)
    
    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": "user_a_token"})
    return response.json()

@pytest.fixture(scope="module")
async def authenticated_user_b(async_client: AsyncClient, monkeypatch) -> dict:
    """Фикстура для создания и аутентификации второго пользователя (User B)."""
    async def mock_is_token_valid(token):
        return 900000002
    monkeypatch.setattr("app.api.endpoints.auth.is_token_valid", mock_is_token_valid)

    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": "user_b_token"})
    return response.json()


async def test_scenario_access_unauthenticated(async_client: AsyncClient):
    """Тест: неаутентифицированный пользователь не может получить доступ к сценариям."""
    response = await async_client.get("/api/v1/scenarios")
    assert response.status_code == 401


async def test_create_and_read_scenario(async_client: AsyncClient, authenticated_user_a: dict):
    """
    Комплексный тест:
    1. Создаем сценарий под пользователем А.
    2. Проверяем, что он создался.
    3. Запрашиваем список сценариев и проверяем, что он там есть.
    4. Запрашиваем конкретно этот сценарий по ID.
    """
    headers = {"Authorization": f"Bearer {authenticated_user_a['access_token']}"}

    # 1. Создание
    create_response = await async_client.post("/api/v1/scenarios", headers=headers, json=SCENARIO_PAYLOAD)
    assert create_response.status_code == 201
    created_data = create_response.json()
    assert created_data["name"] == SCENARIO_PAYLOAD["name"]
    scenario_id = created_data["id"]

    # 2. Чтение списка
    list_response = await async_client.get("/api/v1/scenarios", headers=headers)
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert isinstance(list_data, list)
    assert len(list_data) == 1
    assert list_data[0]["id"] == scenario_id
    assert list_data[0]["name"] == SCENARIO_PAYLOAD["name"]

    # 3. Чтение по ID
    get_response = await async_client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["id"] == scenario_id


async def test_scenario_access_control_isolation(async_client: AsyncClient, authenticated_user_a: dict, authenticated_user_b: dict):
    """
    Тест безопасности: пользователь Б не может получить доступ к сценарию пользователя А.
    """
    headers_a = {"Authorization": f"Bearer {authenticated_user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {authenticated_user_b['access_token']}"}

    # Пользователь А создает сценарий
    create_response = await async_client.post("/api/v1/scenarios", headers=headers_a, json=SCENARIO_PAYLOAD)
    scenario_id_a = create_response.json()["id"]

    # Пользователь Б пытается получить к нему доступ
    response_b = await async_client.get(f"/api/v1/scenarios/{scenario_id_a}", headers=headers_b)
    
    # Ожидаем ошибку 404, так как для пользователя Б этого сценария не существует
    assert response_b.status_code == 404


async def test_update_and_delete_scenario(async_client: AsyncClient, authenticated_user_a: dict):
    """
    Тест обновления и удаления сценария.
    """
    headers = {"Authorization": f"Bearer {authenticated_user_a['access_token']}"}
    
    # Сначала создаем сценарий, который будем менять
    create_response = await async_client.post("/api/v1/scenarios", headers=headers, json=SCENARIO_PAYLOAD)
    scenario_id = create_response.json()["id"]

    # Обновляем его
    update_payload = {**SCENARIO_PAYLOAD, "name": "Обновленное имя"}
    update_response = await async_client.put(f"/api/v1/scenarios/{scenario_id}", headers=headers, json=update_payload)
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Обновленное имя"

    # Удаляем его
    delete_response = await async_client.delete(f"/api/v1/scenarios/{scenario_id}", headers=headers)
    assert delete_response.status_code == 204

    # Проверяем, что он действительно удален
    get_response = await async_client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
    assert get_response.status_code == 404