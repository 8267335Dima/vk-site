from sqladmin import BaseView, expose
from fastapi import Request
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import TaskHistory

class DashboardView(BaseView):
    name = "Анализ Производительности"
    icon = "fa-solid fa-gauge-high"
    
    @expose("/admin/dashboard", methods=["GET"])
    async def dashboard_page(self, request: Request):
        session: AsyncSession = request.state.session
        
        duration_sec = func.extract('epoch', TaskHistory.finished_at - TaskHistory.started_at)

        avg_duration_subq = (
            select(
                TaskHistory.task_name,
                func.avg(duration_sec).label("avg_duration")
            )
            .where(TaskHistory.status == "SUCCESS", TaskHistory.started_at.is_not(None), TaskHistory.finished_at.is_not(None))
            .group_by(TaskHistory.task_name)
            .subquery()
        )

        status_counts_subq = (
            select(
                TaskHistory.task_name,
                func.count().label("total_runs"),
                func.sum(case((TaskHistory.status == "FAILURE", 1), else_=0)).label("failure_count")
            )
            .group_by(TaskHistory.task_name)
            .subquery()
        )

        stmt = (
            select(
                status_counts_subq.c.task_name,
                status_counts_subq.c.total_runs,
                status_counts_subq.c.failure_count,
                avg_duration_subq.c.avg_duration
            )
            .join(
                avg_duration_subq,
                status_counts_subq.c.task_name == avg_duration_subq.c.task_name,
                isouter=True
            )
            .order_by(status_counts_subq.c.total_runs.desc())
        )
        
        result = await session.execute(stmt)
        performance_data = []
        for row in result.all():
            failure_rate = (row.failure_count / row.total_runs * 100) if row.total_runs > 0 else 0
            performance_data.append({
                "task_name": row.task_name,
                "total_runs": row.total_runs,
                "failure_rate": round(failure_rate, 2),
                "avg_duration": round(row.avg_duration, 2) if row.avg_duration else "N/A"
            })

        return await self.templates.TemplateResponse(
            "admin/dashboard.html",
            {"request": request, "performance_data": performance_data}
        )