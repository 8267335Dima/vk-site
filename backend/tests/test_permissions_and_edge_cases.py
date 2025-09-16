# backend/tests/test_permissions_and_edge_cases.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.db.models import User
from app.core.constants import PlanName
from app.services.vk_api import VKAPIError


async def test_pro_feature_access_denied_for_plus_user(db_session: AsyncSession, async_client: AsyncClient, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    
    # Понижаем тариф до Plus
    user.plan = PlanName.PLUS
    await db_session.commit()

    # Пытаемся использовать PRO-фичу (смена скорости)
    response = await async_client.put("/api/v1/users/me/delay-profile", headers=headers, json={"delay_profile": "fast"})
    assert response.status_code == 403
    assert "Смена скорости доступна только на PRO тарифе" in response.text

    # Возвращаем тариф
    user.plan = PlanName.PRO
    await db_session.commit()
    
async def test_get_task_info_endpoint(async_client: AsyncClient, authorized_user_and_headers: tuple):
    _, headers = authorized_user_and_headers
    
    # Проверяем инфо для входящих заявок
    response_accept = await async_client.get("/api/v1/users/task-info?task_key=accept_friends", headers=headers)
    assert response_accept.status_code == 200
    assert "count" in response_accept.json()
    
    # Проверяем инфо для удаления друзей
    response_remove = await async_client.get("/api/v1/users/task-info?task_key=remove_friends", headers=headers)
    assert response_remove.status_code == 200
    assert response_remove.json()['count'] > 0

@patch('app.services.outgoing_request_service.OutgoingRequestService.get_add_recommended_targets', side_effect=VKAPIError("Test API Error", 5))
async def test_preview_endpoint_handles_vk_error(mock_get_targets, async_client: AsyncClient, authorized_user_and_headers: tuple):
    _, headers = authorized_user_and_headers
    
    payload = {"count": 10, "filters": {}}
    response = await async_client.post("/api/v1/tasks/preview/add_recommended", headers=headers, json=payload)
    
    assert response.status_code == 424 # Failed Dependency
    assert "Ошибка VK API: Test API Error" in response.text