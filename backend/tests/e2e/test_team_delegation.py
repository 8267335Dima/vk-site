# tests/e2e/test_team_delegation.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock
from datetime import datetime, UTC, timedelta

from app.db.models import User, Team, TeamMember, TeamProfileAccess, ManagedProfile, ScheduledPost, ScheduledPostStatus, Notification
from app.tasks.system_tasks import publish_scheduled_post_task

pytestmark = pytest.mark.anyio

async def test_full_team_delegation_and_action_e2e(
    async_client: AsyncClient,
    db_session: AsyncSession,
    manager_user: User,
    team_member_user: User,
    managed_profile_user: User,
    get_auth_headers_for,
    mocker
):
    """
    E2E Тест:
    1. Менеджер дает члену команды доступ к управляемому профилю.
    2. Член команды, переключившись на этот профиль, планирует для него пост.
    3. Фоновая задача публикует этот пост от имени управляемого профиля.
    4. Проверяем, что пост опубликован и уведомление пришло управляемому профилю (а не члену команды).
    """
    # Arrange (Phase 1): Настройка прав
    team = Team(owner_id=manager_user.id, name="E2E Team")
    member = TeamMember(team=team, user_id=team_member_user.id)
    access = TeamProfileAccess(team_member=member, profile_user_id=managed_profile_user.id)
    managed_rel = ManagedProfile(manager_user_id=manager_user.id, profile_user_id=managed_profile_user.id)
    db_session.add_all([team, member, access, managed_rel])
    await db_session.commit()

    # Act (Phase 1): Член команды переключается и планирует пост
    team_member_headers = get_auth_headers_for(team_member_user)
    
    response_switch = await async_client.post(
        "/api/v1/auth/switch-profile",
        headers=team_member_headers,
        json={"profile_id": managed_profile_user.id}
    )
    assert response_switch.status_code == 200
    impersonation_token = response_switch.json()["access_token"]
    impersonation_headers = {"Authorization": f"Bearer {impersonation_token}"}

    post_data = {
        "posts": [{"post_text": "Пост от имени команды", "publish_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}]
    }
    response_schedule = await async_client.post(
        "/api/v1/posts/schedule-batch",
        headers=impersonation_headers,
        json=post_data
    )
    assert response_schedule.status_code == 201
    
    post_id = response_schedule.json()[0]["id"]
    
    # Arrange (Phase 2): Мокаем VK API и emitter для фоновой задачи
    mock_vk_api_class = mocker.patch('app.tasks.system_tasks.VKAPI')
    mock_instance = mock_vk_api_class.return_value
    mock_instance.wall.post = AsyncMock(return_value={"post_id": 555})
    mock_instance.close = AsyncMock()
    
    mock_emitter_class = mocker.patch('app.tasks.system_tasks.RedisEventEmitter')
    mock_emitter_instance = mock_emitter_class.return_value
    async def fake_send_notification(session, message, level):
        post = await session.get(ScheduledPost, post_id)
        # Уведомление создается для владельца поста
        notification = Notification(user_id=post.user_id, message=message, level=level)
        session.add(notification)
        await session.flush()
    mock_emitter_instance.send_system_notification = AsyncMock(side_effect=fake_send_notification)

    # Act (Phase 2): Запускаем фоновую задачу
    await publish_scheduled_post_task(
        ctx={"redis_pool": AsyncMock()},
        post_id=post_id,
        db_session_for_test=db_session
    )
    await db_session.commit()

    # Assert: Проверяем результат
    final_post = await db_session.get(ScheduledPost, post_id)
    assert final_post.status == ScheduledPostStatus.published
    # Убеждаемся, что пост принадлежит именно управляемому профилю
    assert final_post.user_id == managed_profile_user.id

    notification = await db_session.get(Notification, 1)
    assert notification is not None
    # Убеждаемся, что уведомление пришло владельцу профиля, а не члену команды
    assert notification.user_id == managed_profile_user.id