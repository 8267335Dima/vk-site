# backend/app/admin/views/support/ticket.py

import datetime
from fastapi import Request
from fastapi.responses import JSONResponse
from sqladmin import ModelView, action
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timezone

from app.db.models import SupportTicket, TicketStatus
from sqladmin.filters import AllUniqueStringValuesFilter

class SupportTicketAdmin(ModelView, model=SupportTicket):
    category = "Техподдержка"
    name = "Тикет"
    name_plural = "Тикеты"
    icon = "fa-solid fa-headset"
    can_edit = True
    can_create = True
    
    column_list = [SupportTicket.id, "user", SupportTicket.subject, SupportTicket.status, SupportTicket.reopen_count, SupportTicket.updated_at]
    column_details_list = [SupportTicket.id, SupportTicket.user, SupportTicket.subject, SupportTicket.status, SupportTicket.reopen_count, SupportTicket.created_at, SupportTicket.updated_at, SupportTicket.messages]
    column_searchable_list = [SupportTicket.id, SupportTicket.subject, "user.vk_id"]
    column_filters = [AllUniqueStringValuesFilter(SupportTicket.status)]
    column_default_sort = ("updated_at", True)
    form_excluded_columns = [SupportTicket.created_at, SupportTicket.updated_at, SupportTicket.messages, SupportTicket.reopen_count]

    column_formatters = {
        "user": lambda m, a: f"User {m.user.vk_id}" if m.user else "Unknown"
    }

    async def on_model_change(self, data: dict, model: SupportTicket, is_created: bool, request: Request) -> None:
        model.updated_at = datetime.datetime.now(timezone.utc)

    @action(name="reopen_tickets", label="↩️ Переоткрыть")
    async def reopen_tickets(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        pks_int = [int(pk) for pk in pks]
        if pks_int:
            result = await session.execute(select(SupportTicket).where(SupportTicket.id.in_(pks_int)))
            for ticket in result.scalars().all():
                ticket.status=TicketStatus.OPEN
                ticket.updated_at=datetime.datetime.now(timezone.utc)
            await session.commit()
        return JSONResponse(content={"message": f"Переоткрыто тикетов: {len(pks)}"})

    @action(name="resolve_tickets", label="✅ Решить и закрыть")
    async def resolve_tickets(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        pks_int = [int(pk) for pk in pks]
        if pks_int:
            result = await session.execute(select(SupportTicket).where(SupportTicket.id.in_(pks_int)))
            for ticket in result.scalars().all():
                ticket.status=TicketStatus.RESOLVED
                ticket.updated_at=datetime.datetime.now(timezone.utc)
            await session.commit()
        return JSONResponse(content={"message": f"Решено тикетов: {len(pks)}"})

    @action(name="close_permanently", label="🔒 Закрыть навсегда")
    async def close_permanently(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        pks_int = [int(pk) for pk in pks]
        if pks_int:
            result = await session.execute(select(SupportTicket).where(SupportTicket.id.in_(pks_int)))
            for ticket in result.scalars().all():
                ticket.status=TicketStatus.CLOSED
                ticket.updated_at=datetime.datetime.now(timezone.utc)
            await session.commit()
        return JSONResponse(content={"message": f"Закрыто навсегда тикетов: {len(pks)}"})