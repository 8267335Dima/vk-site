# backend/app/api/endpoints/teams.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select, delete
from typing import List

from app.db.session import get_db
from app.db.models import User, Team, TeamMember, ManagedProfile, TeamProfileAccess
from app.api.dependencies import get_current_manager_user
from app.api.schemas.teams import TeamRead, InviteMemberRequest, UpdateAccessRequest, TeamMemberRead, ProfileInfo, TeamMemberAccess
from app.core.plans import is_feature_available_for_plan, get_plan_config
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.core.constants import FeatureKey
import structlog

log = structlog.get_logger(__name__)
router = APIRouter()

async def check_agency_plan(manager: User = Depends(get_current_manager_user)):
    if not is_feature_available_for_plan(manager.plan, FeatureKey.AGENCY_MODE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Управление командой доступно только на тарифе 'Agency'."
        )
    return manager

async def get_team_owner(manager: User = Depends(check_agency_plan), db: AsyncSession = Depends(get_db)):
    stmt = select(Team).where(Team.owner_id == manager.id)
    team = (await db.execute(stmt)).scalar_one_or_none()
    if not team:
        team = Team(name=f"Команда {manager.id}", owner_id=manager.id)
        db.add(team)
        await db.commit()
        await db.refresh(team)
    return manager, team

@router.get("/my-team", response_model=TeamRead)
async def get_my_team(
    manager_and_team: tuple = Depends(get_team_owner),
    db: AsyncSession = Depends(get_db)
):
    manager, team = manager_and_team
    
    # --- ШАГ 1: Загружаем все необходимые данные из НАШЕЙ БД одним запросом ---
    stmt = (
        select(Team)
        .options(
            selectinload(Team.members).selectinload(TeamMember.user),
            selectinload(Team.members).selectinload(TeamMember.profile_accesses)
        )
        .where(Team.id == team.id)
    )
    team_details = (await db.execute(stmt)).scalar_one()

    managed_profiles_db = (await db.execute(
        select(ManagedProfile)
        .options(selectinload(ManagedProfile.profile))
        .where(ManagedProfile.manager_user_id == manager.id)
    )).scalars().all()
    
    # --- ШАГ 2: Собираем ВСЕ уникальные VK ID, которые нужно обогатить данными из VK ---
    all_vk_ids_to_fetch = set()
    # Добавляем VK ID всех участников команды
    for member in team_details.members:
        all_vk_ids_to_fetch.add(member.user.vk_id)
    # Добавляем VK ID всех управляемых профилей
    for mp in managed_profiles_db:
        all_vk_ids_to_fetch.add(mp.profile.vk_id)
    # Добавляем VK ID самого менеджера
    all_vk_ids_to_fetch.add(manager.vk_id)

    # --- ШАГ 3: Делаем ОДИН пакетный запрос к VK API ---
    vk_info_map = {}
    if all_vk_ids_to_fetch:
        vk_api = VKAPI(decrypt_data(manager.encrypted_vk_token))
        vk_ids_str = ",".join(map(str, all_vk_ids_to_fetch))
        user_infos = await vk_api.get_user_info(user_ids=vk_ids_str, fields="photo_50")
        if user_infos:
            vk_info_map = {info['id']: info for info in user_infos}

    # --- ШАГ 4: Собираем ответ, используя предзагруженные данные ---
    members_response = []
    for member in team_details.members:
        member_vk_info = vk_info_map.get(member.user.vk_id, {})
        
        accesses = []
        member_access_map = {pa.profile_user_id for pa in member.profile_accesses}
        
        # Собираем все профили, к которым может быть доступ
        all_available_profiles = [mp.profile for mp in managed_profiles_db]
        
        for profile in all_available_profiles:
            profile_vk_info = vk_info_map.get(profile.vk_id, {})
            accesses.append(TeamMemberAccess(
                profile=ProfileInfo(
                    id=profile.id, vk_id=profile.vk_id,
                    first_name=profile_vk_info.get("first_name", "N/A"),
                    last_name=profile_vk_info.get("last_name", ""),
                    photo_50=profile_vk_info.get("photo_50", "")
                ),
                has_access=profile.id in member_access_map
            ))
            
        members_response.append(TeamMemberRead(
            id=member.id, user_id=member.user_id, role=member.role.value,
            user_info=ProfileInfo(
                id=member.user.id, vk_id=member.user.vk_id,
                first_name=member_vk_info.get("first_name", "N/A"),
                last_name=member_vk_info.get("last_name", ""),
                photo_50=member_vk_info.get("photo_50", "")
            ),
            accesses=accesses
        ))
    
    return TeamRead(id=team.id, name=team.name, owner_id=team.owner_id, members=members_response)


@router.post("/my-team/members", status_code=status.HTTP_201_CREATED)
async def invite_member(
    invite_data: InviteMemberRequest,
    manager_and_team: tuple = Depends(get_team_owner),
    db: AsyncSession = Depends(get_db)
):
    manager, team = manager_and_team
    
    # Загружаем актуальное количество участников
    await db.refresh(team, attribute_names=['members'])

    plan_config = get_plan_config(manager.plan)
    max_members = plan_config.get("limits", {}).get("max_team_members", 1)
    if len(team.members) >= max_members:
        raise HTTPException(status_code=403, detail=f"Достигнут лимит на количество участников в команде ({max_members}).")

    invited_user = (await db.execute(select(User).where(User.vk_id == invite_data.user_vk_id))).scalar_one_or_none()
    if not invited_user:
        raise HTTPException(status_code=404, detail="Пользователь с таким VK ID не найден в системе Zenith.")
    
    stmt_check_member = select(TeamMember).where(TeamMember.user_id == invited_user.id)
    existing_membership = (await db.execute(stmt_check_member)).scalar_one_or_none()
    if existing_membership:
        raise HTTPException(status_code=409, detail="Этот пользователь уже состоит в команде.")

    new_member = TeamMember(team_id=team.id, user_id=invited_user.id)
    db.add(new_member)
    await db.commit()
    return {"message": "Пользователь успешно добавлен в команду."}

@router.delete("/my-team/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: int,
    manager_and_team: tuple = Depends(get_team_owner),
    db: AsyncSession = Depends(get_db)
):
    _, team = manager_and_team
    member = (await db.execute(select(TeamMember).where(TeamMember.id == member_id, TeamMember.team_id == team.id))).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Участник команды не найден.")
    if member.user_id == team.owner_id:
        raise HTTPException(status_code=400, detail="Нельзя удалить владельца команды.")
        
    await db.delete(member)
    await db.commit()

@router.put("/my-team/members/{member_id}/access")
async def update_member_access(
    member_id: int,
    access_data: List[UpdateAccessRequest],
    manager_and_team: tuple = Depends(get_team_owner),
    db: AsyncSession = Depends(get_db)
):
    manager, team = manager_and_team
    member = (await db.execute(select(TeamMember).where(TeamMember.id == member_id, TeamMember.team_id == team.id))).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Участник команды не найден.")

    # Проверяем, что все profile_user_id принадлежат менеджеру
    managed_profiles_stmt = select(ManagedProfile.profile_user_id).where(ManagedProfile.manager_user_id == manager.id)
    managed_ids = (await db.execute(managed_profiles_stmt)).scalars().all()
    
    for access in access_data:
        if access.profile_user_id not in managed_ids and access.profile_user_id != manager.id:
            raise HTTPException(status_code=403, detail=f"Доступ к профилю {access.profile_user_id} не может быть предоставлен.")

    await db.execute(delete(TeamProfileAccess).where(TeamProfileAccess.team_member_id == member_id))
    
    accesses_to_add = [
        TeamProfileAccess(team_member_id=member_id, profile_user_id=access.profile_user_id)
        for access in access_data if access.has_access
    ]
    
    if accesses_to_add:
        db.add_all(accesses_to_add)
        
    await db.commit()
    return {"message": "Права доступа обновлены."}