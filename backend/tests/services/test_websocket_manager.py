# tests/services/test_websocket_manager.py

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
import json

from app.services.websocket_manager import redis_listener, manager

pytestmark = pytest.mark.asyncio

class TestRedisListener:

    @patch("app.services.websocket_manager.manager.broadcast_to_user", new_callable=AsyncMock)
    async def test_listener_parses_message_and_broadcasts(self, mock_broadcast: AsyncMock):
        """
        Тест: проверяет, что слушатель Redis корректно парсит сообщение
        и вызывает метод менеджера для отправки его клиенту.
        """
        # Arrange
        user_id = 123
        payload = {"type": "test", "data": "hello"}
        
        # Мок для pubsub, который вернет наше сообщение и затем завершится
        mock_pubsub = AsyncMock()
        # get_message должен вернуть одно сообщение, а потом None, чтобы цикл завершился
        mock_pubsub.get_message.side_effect = [
            {
                "channel": f"ws:user:{user_id}".encode('utf-8'),
                "data": json.dumps(payload).encode('utf-8')
            },
            # Имитируем прерывание цикла после одного сообщения
            asyncio.CancelledError
        ]
        
        mock_redis_client = AsyncMock()
        mock_redis_client.pubsub.return_value.__aenter__.return_value = mock_pubsub

        # Act
        try:
            await redis_listener(mock_redis_client)
        except asyncio.CancelledError:
            pass # Ожидаемое завершение

        # Assert
        # Проверяем, что broadcast_to_user был вызван с правильным user_id и сообщением
        mock_broadcast.assert_awaited_once_with(
            user_id,
            json.dumps(payload)
        )