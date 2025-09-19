# tests/services/test_group_management_service.py

import pytest
from unittest.mock import AsyncMock

from app.services.group_management_service import GroupManagementService
# ▼▼▼ ИЗМЕНЕНИЕ 1: Импортируем ActionFilters для корректного создания фильтров ▼▼▼
from app.api.schemas.actions import JoinGroupsRequest, ActionFilters
from app.db.models import User

pytestmark = pytest.mark.anyio

async def test_get_join_groups_targets_filters_out_existing_groups(
    db_session, test_user: User, mock_emitter
):
    """
    Тест проверяет, что сервис для вступления в группы корректно отфильтровывает
    сообщества, в которых пользователь уже состоит.
    """
    # Arrange
    service = GroupManagementService(db=db_session, user=test_user, emitter=mock_emitter)

    mock_vk_api = AsyncMock()
    # Мокаем поиск: VK нашел 3 группы
    mock_vk_api.groups.search.return_value = {
        "count": 3,
        "items": [
            {"id": 101, "name": "New Group 1", "is_closed": 0},
            {"id": 102, "name": "Existing Group", "is_closed": 0},
            {"id": 103, "name": "New Group 2", "is_closed": 0},
        ]
    }
    # Мокаем список групп пользователя: он уже состоит в группе 102
    mock_vk_api.groups.get.return_value = {"count": 1, "items": [102]}
    service.vk_api = mock_vk_api
    
    # ▼▼▼ ИЗМЕНЕНИЕ 2: Добавляем ключевое слово, чтобы пройти валидацию в сервисе ▼▼▼
    params = JoinGroupsRequest(
        count=10, 
        filters=ActionFilters(status_keyword="test")
    )

    # Act
    targets = await service.get_join_groups_targets(params)

    # Assert
    assert len(targets) == 2
    target_ids = {t['id'] for t in targets}
    assert target_ids == {101, 103}