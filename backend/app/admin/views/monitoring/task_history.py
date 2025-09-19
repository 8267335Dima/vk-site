# backend/app/admin/views/monitoring/task_history.py

from sqladmin import ModelView, action
from app.db.models import TaskHistory
from sqladmin.filters import AllUniqueStringValuesFilter
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
    async def mark_as_successful(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        pks_int = [int(pk) for pk in pks]
        if pks_int:
            result = await session.execute(select(TaskHistory).where(TaskHistory.id.in_(pks_int)))
            for task in result.scalars().all():
                task.status="SUCCESS"
                task.result="Статус изменен администратором."
            await session.commit()
        return JSONResponse(content={"message": f"Статус изменен для {len(pks)} задач."})

    @action(name="cancel_manually", label="↩️ Отменить (административно)")
    async def cancel_manually(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        pks_int = [int(pk) for pk in pks]
        if pks_int:
            result = await session.execute(select(TaskHistory).where(TaskHistory.id.in_(pks_int)))
            for task in result.scalars().all():
                task.status="CANCELLED"
                task.result="Задача отменена администратором."
            await session.commit()
        return JSONResponse(content={"message": f"Отменено (административно) {len(pks)} задач."})