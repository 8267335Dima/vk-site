from fastapi import Request
from sqladmin import ModelView, action
from app.db.models import SupportTicket, TicketMessage, TicketStatus, User
from app.core.config import settings
from app.db.session import AsyncSessionFactory

class TicketMessageAdmin(ModelView, model=TicketMessage):
    """Inline-представление для сообщений внутри тикета."""
    can_create = True
    can_edit = False
    can_delete = False
    can_list = False
    column_list = [TicketMessage.author, TicketMessage.message, TicketMessage.created_at]
    
    async def on_model_change(self, data: dict, model: TicketMessage, is_created: bool, request: Request) -> None:
        if is_created:
            async with AsyncSessionFactory() as session:
                admin_user = await session.get(User, int(settings.ADMIN_VK_ID))
                if admin_user:
                    model.author_id = admin_user.id
                    
                    # Обновляем статус тикета и время
                    ticket = await session.get(SupportTicket, model.ticket_id)
                    if ticket:
                        ticket.status = TicketStatus.IN_PROGRESS
                        ticket.updated_at = datetime.datetime.utcnow()

class SupportTicketAdmin(ModelView, model=SupportTicket):
    name = "Тикет"
    name_plural = "Техподдержка"
    icon = "fa-solid fa-headset"
    
    column_list = [SupportTicket.id, SupportTicket.user, SupportTicket.subject, SupportTicket.status, SupportTicket.updated_at]
    column_details_list = [SupportTicket.id, SupportTicket.user, SupportTicket.subject, SupportTicket.status, SupportTicket.created_at, SupportTicket.updated_at, SupportTicket.messages]
    
    column_searchable_list = [SupportTicket.id, SupportTicket.subject, "user.vk_id"]
    column_filters = [SupportTicket.status]
    column_default_sort = ("updated_at", True)
    
    form_excluded_columns = [SupportTicket.created_at, SupportTicket.updated_at]
    form_include_related = {"messages": {"model": TicketMessageAdmin}}

    @action(
        name="close_tickets", label="Закрыть тикет(ы)",
        confirmation_message="Уверены, что хотите закрыть выбранные тикеты?",
        add_in_list=True, add_in_detail=True
    )
    async def close_tickets_action(self, request: Request, pks: list[int]):
        async with AsyncSessionFactory() as session:
            for pk in pks:
                ticket = await session.get(SupportTicket, pk)
                if ticket:
                    ticket.status = TicketStatus.CLOSED
            await session.commit()
        return {"message": f"Закрыто тикетов: {len(pks)}"}