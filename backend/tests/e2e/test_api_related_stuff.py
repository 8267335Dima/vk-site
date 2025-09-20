# tests/e2e/test_api_related_stuff.py

import pytest
import json
import asyncio
from fastapi.testclient import TestClient

from app.db.models import User
# Импортируем наш менеджер веб-сокетов напрямую
from app.services.websocket_manager import manager 

def test_websocket_broadcast_delivers_message(
    client: TestClient,
    test_user: User,
    auth_headers: dict
):
    """
    Тест проверяет, что WebSocket-клиент получает сообщение,
    когда оно отправляется через WebSocketManager, БЕЗ участия Redis.
    """
    token = auth_headers["Authorization"].split(" ")[1]
    url_path = f"/api/v1/ws?token={token}"

    log_payload = {
        "type": "log",
        "payload": {"message": "Hello from a direct broadcast!", "status": "info"}
    }
    message_str = json.dumps(log_payload)

    try:
        # 1. Подключаемся к сокету. Теперь он зарегистрирован в 'manager'.
        with client.websocket_connect(url_path) as websocket:
            
            # 2. Напрямую вызываем метод менеджера, чтобы отправить сообщение.
            #    Это имитирует то, что сделал бы Redis listener.
            #    Запускаем эту единственную асинхронную операцию через asyncio.run()
            asyncio.run(manager.broadcast_to_user(test_user.id, message_str))

            # 3. Сразу же получаем сообщение, которое менеджер отправил.
            received_data = websocket.receive_json()

            # 4. Проверяем результат.
            assert received_data["type"] == "log"
            assert received_data["payload"]["message"] == "Hello from a direct broadcast!"

    except Exception as e:
        pytest.fail(f"Тест веб-сокета упал с ошибкой: {e}")