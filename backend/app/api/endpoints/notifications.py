# backend/app/api/endpoints/notifications.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.db.session import get_db
from app.db.models import User, Notification
from app.api.dependencies import get_current_user
from app.api.schemas.notifications import NotificationsResponse

router = APIRouter()

@router.get("", response_model=NotificationsResponse)
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает последние 50 уведомлений и количество непрочитанных."""
    
    # Запрос на получение уведомлений
    query = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    result = await db.execute(query)
    notifications = result.scalars().all()

    # Запрос на подсчет непрочитанных
    count_query = (
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    count_result = await db.execute(count_query)
    unread_count = count_result.scalar_one()

    return NotificationsResponse(items=notifications, unread_count=unread_count)

@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Отмечает все уведомления пользователя как прочитанные."""
    stmt = (
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()