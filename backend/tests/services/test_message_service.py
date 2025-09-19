# tests/services/test_message_service.py

import pytest
from unittest.mock import AsyncMock

from app.services.message_service import MessageService
from app.db.models import User

pytestmark = pytest.mark.anyio

# Мок-данные: 4 цели для рассылки
TARGETS_MOCK = [
    {"id": 1, "first_name": "User1"},
    {"id": 2, "first_name": "User2"},
    {"id": 3, "first_name": "User3"},
    {"id": 4, "first_name": "User4"},
]

@pytest.mark.parametrize("only_new, only_unread, mock_convs, expected_ids", [
    # 1. Фильтр "Только новые диалоги". У нас уже есть диалоги с ID 1 и 3. Остаться должны 2 и 4.
    (True, False, {"items": [
        {"conversation": {"peer": {"id": 1}}},
        {"conversation": {"peer": {"id": 3}}}
    ]}, {2, 4}),
    
    # 2. Фильтр "Только непрочитанные". Непрочитанные - с ID 3 и 4. Они и должны остаться.
    (False, True, {"items": [
        {"conversation": {"peer": {"id": 3}}},
        {"conversation": {"peer": {"id": 4}}}
    ], "count": 2}, {3, 4}),
    
    # 3. Фильтр "Только непрочитанные", но VK API вернул пустой список. Никто не должен остаться.
    (False, True, {"items": [], "count": 0}, set()),
    
    # 4. Фильтры выключены. Все 4 цели должны остаться.
    (False, False, None, {1, 2, 3, 4})
])
async def test_filter_targets_by_conversation_status(
    db_session, test_user: User, mock_emitter,
    only_new, only_unread, mock_convs, expected_ids
):
    """
    Тестирует логику фильтрации получателей по статусу диалога.
    """
    # Arrange
    service = MessageService(db=db_session, user=test_user, emitter=mock_emitter)
    
    mock_vk_api = AsyncMock()
    # Мокаем нужный метод VK API в зависимости от сценария
    if only_new:
        mock_vk_api.get_conversations.return_value = mock_convs
    if only_unread:
        mock_vk_api.get_conversations.return_value = mock_convs
    service.vk_api = mock_vk_api

    # Act
    result_targets = await service.filter_targets_by_conversation_status(
        TARGETS_MOCK, only_new, only_unread
    )

    # Assert
    result_ids = {t["id"] for t in result_targets}
    assert result_ids == expected_ids