# --- START OF FILE tests/api/test_websockets.py ---

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDenialResponse
from starlette.websockets import WebSocketDisconnect

pytest.importorskip("wsproto")

# ИСПРАВЛЕНИЕ: тесты теперь не async и используют фикстуру 'client'
def test_websocket_connection_success(client: TestClient, auth_headers: dict):
    token = auth_headers["Authorization"].split(" ")[1]
    url_path = f"/api/v1/ws?token={token}"
    
    try:
        with client.websocket_connect(url_path) as websocket:
            # Просто успешное соединение и автоматическое закрытие
            pass
    except Exception as e:
        pytest.fail(f"WebSocket connection to '{url_path}' failed unexpectedly: {e}")

def test_websocket_connection_invalid_token(client: TestClient):
    invalid_token = "this.is.an.invalid.token"
    url_path = f"/api/v1/ws?token={invalid_token}"
    
    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with client.websocket_connect(url_path):
            pass
            
    assert exc_info.value.status_code == 401