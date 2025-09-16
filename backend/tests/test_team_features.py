# backend/tests/test_team_features.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
import random

from app.db.models import User, Team, TeamMember, ManagedProfile, TeamProfileAccess
from app.core.constants import PlanName
from app.core.security import create_access_token


@pytest.fixture
async def team_setup(db_session: AsyncSession, authorized_user_and_headers):
    manager, _ = authorized_user_and_headers
    # Переводим на Agency для теста
    manager.plan = PlanName.AGENCY
    
    # Создаем пользователя-участника
    member_user = User(vk_id=random.randint(2000000000, 3000000000), encrypted_vk_token="fake_member_token")
    
    # Создаем два управляемых профиля
    profile_a = User(vk_id=random.randint(3000000000, 4000000000), encrypted_vk_token="fake_profile_a")
    profile_b = User(vk_id=random.randint(4000000000, 5000000000), encrypted_vk_token="fake_profile_b")
    
    db_session.add_all([manager, member_user, profile_a, profile_b])
    await db_session.commit()

    yield manager, member_user, profile_a, profile_b

    # Очистка
    await db_session.execute(delete(User).where(User.id.in_([member_user.id, profile_a.id, profile_b.id])))
    manager.plan = PlanName.PRO
    await db_session.commit()

async def test_team_member_management(async_client: AsyncClient, authorized_user_and_headers, team_setup):
    manager, member_user, _, _ = team_setup
    _, headers = authorized_user_and_headers

    # Приглашаем участника
    resp_invite = await async_client.post("/api/v1/teams/my-team/members", headers=headers, json={"user_vk_id": member_user.vk_id})
    assert resp_invite.status_code == 201

    # Проверяем, что он в команде
    resp_get_team = await async_client.get("/api/v1/teams/my-team", headers=headers)
    team_data = resp_get_team.json()
    member_in_team = next((m for m in team_data['members'] if m['user_id'] == member_user.id), None)
    assert member_in_team is not None

    # Удаляем участника
    resp_delete = await async_client.delete(f"/api/v1/teams/my-team/members/{member_in_team['id']}", headers=headers)
    assert resp_delete.status_code == 204

async def test_team_access_control(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers, team_setup):
    manager, member, profile_a, profile_b = team_setup
    _, manager_headers = authorized_user_and_headers

    # Создаем связи "менеджер -> управляемый профиль"
    db_session.add_all([
        ManagedProfile(manager_user_id=manager.id, profile_user_id=profile_a.id),
        ManagedProfile(manager_user_id=manager.id, profile_user_id=profile_b.id)
    ])
    # Создаем команду и участника
    team = Team(owner_id=manager.id, name="Test Agency")
    team_member = TeamMember(team=team, user=member)
    db_session.add_all([team, team_member])
    await db_session.commit()

    # Даем доступ только к профилю A
    await async_client.put(f"/api/v1/teams/my-team/members/{team_member.id}/access", headers=manager_headers, json=[
        {"profile_user_id": profile_a.id, "has_access": True},
        {"profile_user_id": profile_b.id, "has_access": False}
    ])

    # Генерируем токен для УЧАСТНИКА КОМАНДЫ
    member_token = create_access_token(data={"sub": str(member.id)})
    member_headers = {"Authorization": f"Bearer {member_token}"}
    
    # Пытаемся переключиться на разрешенный профиль A
    resp_a = await async_client.post("/api/v1/auth/switch-profile", headers=member_headers, json={"profile_id": profile_a.id})
    assert resp_a.status_code == 200

    # Пытаемся переключиться на ЗАПРЕЩЕННЫЙ профиль B
    resp_b = await async_client.post("/api/v1/auth/switch-profile", headers=member_headers, json={"profile_id": profile_b.id})
    assert resp_b.status_code == 403