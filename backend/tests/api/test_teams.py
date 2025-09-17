# tests/api/test_teams.py
import pytest
import pytest_asyncio  # <--- ИСПРАВЛЕНИЕ 1
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from unittest.mock import AsyncMock # <--- ИСПРАВЛЕНИЕ 2

from app.main import app # <--- ИСПРАВЛЕНИЕ 3
from app.db.models import User, Team, TeamMember, ManagedProfile, TeamProfileAccess
from app.api.dependencies import get_current_active_profile

pytestmark = pytest.mark.anyio


@pytest_asyncio.fixture(autouse=True)
async def setup_managed_profile(
    db_session: AsyncSession, manager_user: User, managed_profile_user: User
):
    """Фикстура для автоматического создания связи 'менеджер -> управляемый профиль'."""
    managed_rel = ManagedProfile(
        manager_user_id=manager_user.id,
        profile_user_id=managed_profile_user.id
    )
    db_session.add(managed_rel)
    await db_session.commit()


async def test_manager_invites_team_member(
    async_client: AsyncClient, db_session: AsyncSession, manager_user: User, team_member_user: User, get_auth_headers_for
):
    """
    Тест 1: Менеджер успешно приглашает нового участника в свою команду.
    """
    manager_headers = get_auth_headers_for(manager_user)

    # Переопределяем зависимость, чтобы она возвращала менеджера
    app.dependency_overrides[get_current_active_profile] = lambda: manager_user

    # Действие: Менеджер отправляет приглашение
    response = await async_client.post(
        "/api/v1/teams/my-team/members",
        headers=manager_headers,
        json={"user_vk_id": team_member_user.vk_id}
    )

    # Проверка
    assert response.status_code == 201
    
    team = (await db_session.execute(
        select(Team).where(Team.owner_id == manager_user.id)
    )).scalar_one()
    
    member = (await db_session.execute(
        select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == team_member_user.id)
    )).scalar_one_or_none()

    assert member is not None
    assert member.user_id == team_member_user.id

    # Очистка переопределения
    del app.dependency_overrides[get_current_active_profile]


async def test_manager_grants_access_to_team_member(
    async_client: AsyncClient, db_session: AsyncSession, manager_user: User, team_member_user: User, managed_profile_user: User, get_auth_headers_for
):
    """
    Тест 2: Менеджер предоставляет члену команды доступ к управляемому профилю.
    """
    # --- Подготовка: создаем команду и добавляем участника ---
    team = Team(owner_id=manager_user.id, name=f"Команда {manager_user.vk_id}")
    db_session.add(team)
    await db_session.flush()
    member = TeamMember(team_id=team.id, user_id=team_member_user.id)
    db_session.add(member)
    await db_session.commit()
    # --------------------------------------------------------

    manager_headers = get_auth_headers_for(manager_user)
    app.dependency_overrides[get_current_active_profile] = lambda: manager_user

    access_data = [
        {"profile_user_id": managed_profile_user.id, "has_access": True}
    ]

    # Действие: Менеджер обновляет права доступа
    response = await async_client.put(
        f"/api/v1/teams/my-team/members/{member.id}/access",
        headers=manager_headers,
        json=access_data
    )

    # Проверка
    assert response.status_code == 200
    
    access_record = (await db_session.execute(
        select(TeamProfileAccess).where(
            TeamProfileAccess.team_member_id == member.id,
            TeamProfileAccess.profile_user_id == managed_profile_user.id
        )
    )).scalar_one_or_none()

    assert access_record is not None

    del app.dependency_overrides[get_current_active_profile]


async def test_team_member_switches_profile_and_acts_on_behalf(
    async_client: AsyncClient, db_session: AsyncSession, manager_user: User, team_member_user: User, managed_profile_user: User, get_auth_headers_for, mocker
):
    """
    Тест 3 (Ключевой): Член команды переключается на управляемый профиль
    и успешно получает данные этого профиля через эндпоинт /users/me.
    """
    # --- Полная подготовка сценария ---
    team = Team(owner_id=manager_user.id, name=f"Команда {manager_user.vk_id}")
    db_session.add(team)
    await db_session.flush()
    member = TeamMember(team_id=team.id, user_id=team_member_user.id)
    db_session.add(member)
    await db_session.flush()
    access = TeamProfileAccess(team_member_id=member.id, profile_user_id=managed_profile_user.id)
    db_session.add(access)
    await db_session.commit()
    # ------------------------------------

    # Шаг 1: Член команды логинится и получает свой личный токен
    team_member_headers = get_auth_headers_for(team_member_user)

    # Шаг 2: Член команды запрашивает переключение на управляемый профиль
    app.dependency_overrides[get_current_active_profile] = lambda: team_member_user

    response_switch = await async_client.post(
        "/api/v1/auth/switch-profile",
        headers=team_member_headers,
        json={"profile_id": managed_profile_user.id}
    )
    
    assert response_switch.status_code == 200
    switch_data = response_switch.json()
    
    impersonation_token = switch_data["access_token"]
    impersonation_headers = {"Authorization": f"Bearer {impersonation_token}"}
    
    # Шаг 3: Используя новый токен, запрашиваем /users/me
    del app.dependency_overrides[get_current_active_profile]
    
    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ: Добавляем недостающие поля в мок ---
    mock_vk_api_class = mocker.patch('app.api.endpoints.users.VKAPI')
    mock_instance = mock_vk_api_class.return_value
    
    mock_vk_response = [{
        "id": managed_profile_user.vk_id,
        "first_name": "Managed",
        "last_name": "Profile",
        "photo_200": "https://vk.com/images/camera_200.png", # <-- ДОБАВЛЕНО
        "status": "Test status",                              # <-- ДОБАВЛЕНО
        "counters": {"friends": 100}                         # <-- ДОБАВЛЕНО
    }]
    mock_instance.users.get = AsyncMock(return_value=mock_vk_response)
    mock_instance.close = AsyncMock()
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    response_me = await async_client.get("/api/v1/users/me", headers=impersonation_headers)

    # Проверка: мы должны получить данные УПРАВЛЯЕМОГО ПРОФИЛЯ, а не члена команды
    assert response_me.status_code == 200
    me_data = response_me.json()

    assert me_data["id"] == managed_profile_user.id
    assert me_data["vk_id"] == managed_profile_user.vk_id
    assert me_data["first_name"] == "Managed"
    assert me_data["photo_200"] is not None # Проверяем наличие поля

async def test_removed_team_member_loses_access(
    async_client: AsyncClient, db_session: AsyncSession, manager_user: User, team_member_user: User, managed_profile_user: User, get_auth_headers_for, mocker
):
    """
    Тест: Член команды, удаленный из нее, теряет доступ к управляемым профилям.
    """
    # --- 1. Подготовка: Создаем команду, добавляем участника и даем ему доступ ---
    team = Team(owner_id=manager_user.id, name="Temp Team")
    db_session.add(team)
    await db_session.flush()
    member = TeamMember(team_id=team.id, user_id=team_member_user.id)
    db_session.add(member)
    await db_session.flush()
    access = TeamProfileAccess(team_member_id=member.id, profile_user_id=managed_profile_user.id)
    db_session.add(access)
    await db_session.commit()

    # --- 2. Проверка до удаления: Участник может переключиться на профиль ---
    team_member_headers = get_auth_headers_for(team_member_user)
    app.dependency_overrides[get_current_active_profile] = lambda: team_member_user
    
    response_switch_before = await async_client.post(
        "/api/v1/auth/switch-profile",
        headers=team_member_headers,
        json={"profile_id": managed_profile_user.id}
    )
    assert response_switch_before.status_code == 200
    del app.dependency_overrides[get_current_active_profile]

    # --- 3. Действие: Менеджер удаляет участника из команды ---
    manager_headers = get_auth_headers_for(manager_user)
    app.dependency_overrides[get_current_active_profile] = lambda: manager_user

    response_delete = await async_client.delete(
        f"/api/v1/teams/my-team/members/{member.id}",
        headers=manager_headers
    )
    assert response_delete.status_code == 204
    del app.dependency_overrides[get_current_active_profile]

    # --- 4. Проверка после удаления: Участник больше не может переключиться на профиль ---
    app.dependency_overrides[get_current_active_profile] = lambda: team_member_user
    
    response_switch_after = await async_client.post(
        "/api/v1/auth/switch-profile",
        headers=team_member_headers,
        json={"profile_id": managed_profile_user.id}
    )
    assert response_switch_after.status_code == 403 # Ожидаем ошибку "Доступ запрещен"
    assert "Доступ к этому профилю запрещен" in response_switch_after.json()["detail"]
    
    del app.dependency_overrides[get_current_active_profile]