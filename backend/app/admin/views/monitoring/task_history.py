from sqladmin import ModelView, action
from app.db.models import TaskHistory
from sqladmin.filters import AllUniqueStringValuesFilter
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

class TaskHistoryAdmin(ModelView, model=TaskHistory):
    category = "Мониторинг"
    name = "История Задач"
    name_plural = "История Задач"
    icon = "fa-solid fa-history"
    can_create = False
    can_edit = False
    can_delete = True
    
    column_list = [TaskHistory.id, "user", TaskHistory.task_name, TaskHistory.status, TaskHistory.created_at, TaskHistory.updated_at]
    column_joined_list = [TaskHistory.user]
    column_searchable_list = [TaskHistory.user_id, "user.vk_id", TaskHistory.task_name]
    column_filters = [AllUniqueStringValuesFilter(TaskHistory.status)]
    column_default_sort = ("created_at", True)
    column_formatters = { "user": lambda m, a: f"User {m.user.vk_id}" if m.user else "Unknown" }

    @action(name="mark_as_successful", label="✅ Пометить как Успешная")
    async def mark_as_successful(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        for pk in pks:
            task = await session.get(TaskHistory, pk)
            if task and task.status == "FAILURE":
                task.status = "SUCCESS"
                task.result = "Статус изменен администратором."
        await session.commit()
        return {"message": f"Статус изменен для {len(pks)} задач."}

    @action(name="cancel_manually", label="↩️ Отменить (административно)")
    async def cancel_manually(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        for pk in pks:
            task = await session.get(TaskHistory, pk)
            if task and task.status in ["SUCCESS", "FAILURE"]:
                task.status = "CANCELLED"
                task.result = "Задача отменена администратором."
        await session.commit()
        return {"message": f"Отменено (административно) {len(pks)} задач."}