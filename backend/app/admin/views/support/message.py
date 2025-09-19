from sqladmin import ModelView
from app.db.models import TicketMessage

class TicketMessageAdmin(ModelView, model=TicketMessage):
    category = "Техподдержка"
    name = "Сообщение"
    name_plural = "Все Сообщения"
    icon = "fa-solid fa-envelope"
    can_create = False
    can_edit = True
    can_delete = True
    can_list = True
    
    column_list = ["ticket", "author", TicketMessage.message, TicketMessage.created_at]
    column_details_list = [TicketMessage.id, "ticket", "author", TicketMessage.message, TicketMessage.attachment_url, TicketMessage.created_at]
    column_searchable_list = [TicketMessage.message, "author.vk_id", "ticket.id", "ticket.subject"]
    column_default_sort = ("created_at", True)

    column_formatters = {
        "author": lambda m, a: f"User {m.author.vk_id}" if m.author else "Admin"
    }