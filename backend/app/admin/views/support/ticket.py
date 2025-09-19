import datetime
from fastapi import Request
from sqladmin import ModelView, action
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timezone

from app.db.models import SupportTicket, TicketMessage, TicketStatus
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
    async def reopen_tickets(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        for pk in pks:
            ticket = await session.get(SupportTicket, pk)
            if ticket and ticket.status != TicketStatus.OPEN:
                ticket.status = TicketStatus.OPEN
                ticket.updated_at = datetime.datetime.now(timezone.utc)
        await session.commit()
        return {"message": f"Переоткрыто тикетов: {len(pks)}"}

    @action(name="resolve_tickets", label="✅ Решить и закрыть")
    async def resolve_tickets(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        for pk in pks:
            ticket = await session.get(SupportTicket, pk)
            if ticket:
                ticket.status = TicketStatus.RESOLVED
                ticket.updated_at = datetime.datetime.now(timezone.utc)
        await session.commit()
        return {"message": f"Решено тикетов: {len(pks)}"}

    @action(name="close_permanently", label="🔒 Закрыть навсегда")
    async def close_permanently(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        for pk in pks:
            ticket = await session.get(SupportTicket, pk)
            if ticket:
                ticket.status = TicketStatus.CLOSED
                ticket.updated_at = datetime.datetime.now(timezone.utc)
        await session.commit()
        return {"message": f"Закрыто навсегда тикетов: {len(pks)}"}