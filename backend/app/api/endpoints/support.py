import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from typing import List

from app.db.session import get_db
from app.db.models import User, SupportTicket, TicketMessage, TicketStatus
from app.api.dependencies import get_current_active_profile
from app.api.schemas.support import SupportTicketCreate, SupportTicketRead, TicketMessageCreate, SupportTicketList

router = APIRouter()

@router.get("", response_model=List[SupportTicketList])
async def get_my_tickets(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Получить список всех тикетов текущего пользователя."""
    stmt = select(SupportTicket).where(SupportTicket.user_id == current_user.id).order_by(SupportTicket.updated_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("", response_model=SupportTicketRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    ticket_data: SupportTicketCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Создать новый тикет в техподдержку."""
    new_ticket = SupportTicket(
        user_id=current_user.id,
        subject=ticket_data.subject,
        status=TicketStatus.OPEN
    )
    
    first_message = TicketMessage(
        ticket=new_ticket,
        author_id=current_user.id,
        message=ticket_data.message
    )
    
    db.add(new_ticket)
    db.add(first_message)
    await db.commit()
    await db.refresh(new_ticket, attribute_names=['messages'])
    return new_ticket

@router.get("/{ticket_id}", response_model=SupportTicketRead)
async def get_ticket_details(
    ticket_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Получить детали тикета и всю переписку по нему."""
    stmt = select(SupportTicket).where(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == current_user.id
    ).options(selectinload(SupportTicket.messages))
    
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден.")
    
    return ticket

@router.post("/{ticket_id}/messages", response_model=SupportTicketRead)
async def reply_to_ticket(
    ticket_id: int,
    message_data: TicketMessageCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Ответить на тикет."""
    # Получаем тикет и блокируем его для обновления
    stmt = select(SupportTicket).where(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == current_user.id
    ).with_for_update()
    
    ticket = (await db.execute(stmt)).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден.")
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот тикет закрыт.")

    new_message = TicketMessage(
        ticket_id=ticket.id,
        author_id=current_user.id,
        message=message_data.message
    )
    db.add(new_message)
    
    # Меняем статус на OPEN, если на него ответил пользователь (вдруг админ поставил IN_PROGRESS)
    ticket.status = TicketStatus.OPEN
    ticket.updated_at = datetime.datetime.utcnow()
    
    await db.commit()
    await db.refresh(ticket, attribute_names=['messages'])
    return ticket