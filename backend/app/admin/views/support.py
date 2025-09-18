# backend/app/admin/views/support.py
import datetime
from fastapi import Request
from sqladmin import ModelView, action
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timezone

from app.db.models import SupportTicket, TicketMessage, TicketStatus
from sqladmin.filters import AllUniqueStringValuesFilter


class TicketMessageAdmin(ModelView, model=TicketMessage):
    can_create = True
    can_edit = False
    can_delete = False
    can_list = False
    column_list = ["author", TicketMessage.message, TicketMessage.created_at]
    column_details_list = [TicketMessage.author] 

    column_formatters = {
        "author": lambda m, a: f"User {m.author.vk_id}" if m.author else "Unknown"
    }


class SupportTicketAdmin(ModelView, model=SupportTicket):
    identity = "support-ticket"
    name = "Тикет"
    name_plural = "Техподдержка"
    icon = "fa-solid fa-headset"
    can_edit = True

    column_list = [SupportTicket.id, "user", SupportTicket.subject, SupportTicket.status, SupportTicket.reopen_count, SupportTicket.updated_at]
    column_select_related = [SupportTicket.user]
    column_details_list = [SupportTicket.id, SupportTicket.user, SupportTicket.subject, SupportTicket.status, SupportTicket.reopen_count, SupportTicket.created_at, SupportTicket.updated_at, SupportTicket.messages]
    column_searchable_list = [SupportTicket.id, SupportTicket.subject, "user.vk_id"]
    column_filters = [AllUniqueStringValuesFilter(SupportTicket.status)]
    column_default_sort = ("updated_at", True)
    form_excluded_columns = [SupportTicket.created_at, SupportTicket.updated_at, SupportTicket.messages, SupportTicket.reopen_count]

    column_formatters = {
        "user": lambda m, a: f"User {m.user.vk_id}" if m.user else "Unknown"
    }

    async def on_model_change(self, data: dict, model: SupportTicket, is_created: bool, request: Request) -> None:
        if is_created:
            return

        session: AsyncSession = request.state.session
        
        if 'status' in data:
            try:
                status_str = data['status'].upper()
                if status_str in [s.name for s in TicketStatus]:
                    model.status = TicketStatus[status_str]
            except (KeyError, AttributeError):
                pass
        
        model.updated_at = datetime.datetime.now(timezone.utc)

    @action(
        name="resolve_tickets", label="✅ Решить и закрыть (можно переоткрыть)",
        confirmation_message="Уверены? Пользователь сможет переоткрыть тикет.",
        add_in_list=True, add_in_detail=True
    )
    async def resolve_tickets(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        for pk in pks:
            ticket = await session.get(SupportTicket, pk)
            if ticket:
                ticket.status = TicketStatus.RESOLVED # --- ИЗМЕНЕНИЕ ---
                ticket.updated_at = datetime.datetime.now(timezone.utc)
        await session.commit()
        return {"message": f"Решено тикетов: {len(pks)}"}

    @action(
        name="close_permanently", label="🔒 Закрыть навсегда",
        confirmation_message="ВНИМАНИЕ: Пользователь НЕ сможет переоткрыть этот тикет!",
        add_in_list=True, add_in_detail=True
    )
    async def close_permanently(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        for pk in pks:
            ticket = await session.get(SupportTicket, pk)
            if ticket:
                ticket.status = TicketStatus.CLOSED # --- НОВОЕ ДЕЙСТВИЕ ---
                ticket.updated_at = datetime.datetime.now(timezone.utc)
        await session.commit()
        return {"message": f"Закрыто навсегда тикетов: {len(pks)}"}