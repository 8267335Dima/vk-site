# backend/app/api/endpoints/proxies.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import datetime

from app.db.session import get_db
from app.db.models import User, Proxy
from app.api.dependencies import get_current_active_profile
from app.api.schemas.proxies import ProxyCreate, ProxyRead
from app.core.security import encrypt_data, decrypt_data
from app.services.proxy_service import ProxyService
from app.core.plans import is_feature_available_for_plan

router = APIRouter()

async def check_proxy_feature_access(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db) # <--- ДОБАВЛЯЕМ ЗАВИСИМОСТЬ
):
    if not await is_feature_available_for_plan(current_user.plan.name_id, "proxy_management", db=db, user=current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Управление прокси доступно только на PRO-тарифе."
        )
    return current_user

@router.post("", response_model=ProxyRead, status_code=status.HTTP_201_CREATED)
async def add_proxy(
    proxy_data: ProxyCreate,
    current_user: User = Depends(check_proxy_feature_access),
    db: AsyncSession = Depends(get_db)
):
    """Добавляет новый прокси для пользователя и сразу проверяет его."""
    is_working, status_message = await ProxyService.check_proxy(proxy_data.proxy_url)
    
    encrypted_url = encrypt_data(proxy_data.proxy_url)

    stmt_exists = select(Proxy).where(Proxy.user_id == current_user.id, Proxy.encrypted_proxy_url == encrypted_url)
    existing = await db.execute(stmt_exists)
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такой прокси уже существует.")

    new_proxy = Proxy(
        user_id=current_user.id,
        encrypted_proxy_url=encrypted_url,
        is_working=is_working,
        check_status_message=status_message,
        last_checked_at=datetime.datetime.now(datetime.UTC)
    )
    db.add(new_proxy)
    await db.commit()
    await db.refresh(new_proxy)
    
    return ProxyRead(
        id=new_proxy.id,
        proxy_url=decrypt_data(new_proxy.encrypted_proxy_url),
        is_working=new_proxy.is_working,
        last_checked_at=new_proxy.last_checked_at,
        check_status_message=new_proxy.check_status_message
    )

@router.get("", response_model=List[ProxyRead])
async def get_user_proxies(
    current_user: User = Depends(check_proxy_feature_access),
    db: AsyncSession = Depends(get_db)  # <--- ИЗМЕНЕНИЕ 1: Добавлена зависимость
):
    """Возвращает список всех прокси пользователя."""
    await db.refresh(current_user, attribute_names=['proxies'])
    
    return [
        ProxyRead(
            id=p.id,
            proxy_url=decrypt_data(p.encrypted_proxy_url),
            is_working=p.is_working,
            last_checked_at=p.last_checked_at,
            check_status_message=p.check_status_message
        ) for p in current_user.proxies
    ]

@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy(
    proxy_id: int,
    current_user: User = Depends(check_proxy_feature_access),
    db: AsyncSession = Depends(get_db)
):
    """Удаляет прокси по ID."""
    stmt = select(Proxy).where(Proxy.id == proxy_id, Proxy.user_id == current_user.id)
    result = await db.execute(stmt)
    proxy_to_delete = result.scalar_one_or_none()
    
    if not proxy_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Прокси не найден.")
    
    await db.delete(proxy_to_delete)
    await db.commit()