import pytest
from httpx import AsyncClient
from app.core.config import settings

pytestmark = pytest.mark.asyncio

SCENARIO_PAYLOAD = {
    "name": "Сценарий, созданный тестом",
    "schedule": "0 12 * * *",
    "is_active": True,
    "nodes": [{"id": "node-1", "type": "action", "position": {"x": 100, "y": 100}, "data": {"action_type": "start"}}],
    "edges": []
}

async def test_scenario_creation_and_analysis(async_client: AsyncClient):
    """
    Этот тест создаст сценарий в вашей реальной БД и оставит его там для анализа.
    Он не будет его удалять.
    """
    # 1. Логинимся, чтобы получить токен
    test_token = settings.VK_HEALTH_CHECK_TOKEN
    assert test_token, "Переменная VK_HEALTH_CHECK_TOKEN должна быть в .env"
    
    login_response = await async_client.post("/api/v1/auth/vk", json={"vk_token": test_token})
    assert login_response.status_code == 200
    access_token = login_response.json()['access_token']
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Создаем сценарий
    create_response = await async_client.post("/api/v1/scenarios", headers=headers, json=SCENARIO_PAYLOAD)
    
    # Распечатаем ответ от сервера, чтобы вы сразу видели, что пошло не так
    if create_response.status_code != 201:
        print("Тело ответа при ошибке:", create_response.json())
        
    assert create_response.status_code == 201
    print("Сценарий успешно создан в базе данных. Вы можете проверить его.")