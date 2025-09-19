# backend/app/api/endpoints/data.py
from typing import List
from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse
from app.api.dependencies import get_current_active_profile
from app.db.session import get_db
from app.services.data_service import DataService
from app.api.schemas.data import (
    ParsingRequest, GroupMembersParsingRequest, UserWallParsingRequest,
    TopUsersParsingRequest, TopUserResponse
)

router = APIRouter()

@router.post("/parse/group-activity")
async def parse_group_activity(
    request: ParsingRequest,
    user=Depends(get_current_active_profile),
    db=Depends(get_db)
):
    """Запускает парсинг активной аудитории сообщества."""
    service = DataService(db=db, user=user, emitter=None) # Эмиттер не нужен для парсинга
    results = await service.parse_active_group_audience(request.group_id, request.filters)
    return results

@router.get("/export/conversation/{peer_id}")
async def export_conversation(
    peer_id: int,
    user=Depends(get_current_active_profile),
    db=Depends(get_db)
):
    """Скачивает историю переписки с указанным пользователем/чатом."""
    service = DataService(db=db, user=user, emitter=None)
    
    file_name = f"conversation_{peer_id}.json"
    headers = {'Content-Disposition': f'attachment; filename="{file_name}"'}
    
    return StreamingResponse(
        service.export_conversation_as_json(peer_id),
        media_type="application/json",
        headers=headers
    )


@router.post("/parse/group-members")
async def parse_group_members(
    request: GroupMembersParsingRequest, # <-- Теперь это работает
    user=Depends(get_current_active_profile),
    db=Depends(get_db)
):
    """Запускает парсинг подписчиков сообщества."""
    service = DataService(db=db, user=user, emitter=None)
    results = await service.parse_group_members(request.group_id, request.count)
    return results

@router.post("/parse/user-wall")
async def parse_user_wall(
    request: UserWallParsingRequest, # <-- И это тоже работает
    user=Depends(get_current_active_profile),
    db=Depends(get_db)
):
    """Запускает парсинг стены пользователя."""
    service = DataService(db=db, user=user, emitter=None)
    results = await service.parse_user_wall(request.user_id, request.count)
    return results

@router.post("/parse/group-top-active", response_model=List[TopUserResponse])
async def parse_top_active_users(
    request: TopUsersParsingRequest,
    user=Depends(get_current_active_profile),
    db=Depends(get_db)
):
    """Запускает парсинг самых активных пользователей сообщества."""
    service = DataService(db=db, user=user, emitter=None)
    results = await service.parse_top_active_users(request.group_id, request.posts_depth, request.top_n)
    return results