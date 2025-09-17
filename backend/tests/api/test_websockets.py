# tests/api/test_websockets.py
import pytest
from fastapi.testclient import TestClient
# --- ИЗМЕНЕНИЕ: Импортируем WebSocketDenialResponse ---
from starlette.testclient import WebSocketDenialResponse
from starlette.websockets import WebSocketDisconnect

pytest.importorskip("wsproto")

pytestmark = pytest.mark.anyio

async def test_websocket_connection_success(async_client: TestClient, auth_headers: dict):
    token = auth_headers["Authorization"].split(" ")[1]
    url_path = f"/api/v1/ws?token={token}"
    
    try:
        # Эта часть теперь должна работать, т.к. мы исправили зависимость
        with async_client.websocket_connect(url_path) as websocket:
            pass # Успешное соединение и закрытие
    except Exception as e:
        pytest.fail(f"WebSocket connection to '{url_path}' failed unexpectedly: {e}")

async def test_websocket_connection_invalid_token(async_client: TestClient):
    invalid_token = "this.is.an.invalid.token"
    url_path = f"/api/v1/ws?token={invalid_token}"
    
    # --- ИЗМЕНЕНИЕ: Ловим правильное исключение ---
    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with async_client.websocket_connect(url_path):
            pass
            
    # --- ИЗМЕНЕНИЕ: Проверяем статус-код HTTP ответа ---
    assert exc_info.value.status_code == 401