# tests/e2e/test_websockets_e2e.py

import pytest
import json
from fastapi.testclient import TestClient
from redis.asyncio import Redis as AsyncRedis

from app.db.models import User
from app.core.config import settings

pytestmark = pytest.mark.anyio

async def test_message_from_redis_is_delivered_via_websocket(
    client: TestClient, test_user: User, auth_headers: dict
):
    """
    E2E Тест:
    1. Клиент подключается к WebSocket.
    2. Тест напрямую публикует сообщение в Redis Pub/Sub (имитируя работу emitter'а).
    3. Проверяем, что клиент получил это сообщение через WebSocket.
    """
    token = auth_headers["Authorization"].split(" ")[1]
    url_path = f"/api/v1/ws?token={token}"

    # Создаем "публикатора" - отдельный клиент Redis для отправки сообщения
    redis_publisher = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1")

    try:
        # Act (Phase 1): Подключаемся к WebSocket
        with client.websocket_connect(url_path) as websocket:
            
            # Act (Phase 2): Имитируем событие от фоновой задачи, публикуя сообщение в Redis
            log_payload = {
                "type": "log",
                "payload": {
                    "message": "Hello from background task!",
                    "status": "success"
                }
            }
            await redis_publisher.publish(f"ws:user:{test_user.id}", json.dumps(log_payload))

            # Assert: Получаем сообщение из сокета и проверяем его содержимое
            # receive_json() будет ждать сообщение (с таймаутом по умолчанию)
            received_data = websocket.receive_json()
            
            assert received_data["type"] == "log"
            assert received_data["payload"]["message"] == "Hello from background task!"

    finally:
        await redis_publisher.aclose()