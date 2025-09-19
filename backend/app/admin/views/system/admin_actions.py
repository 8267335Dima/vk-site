from sqladmin import BaseView, expose
from fastapi import Request
from sqlalchemy import update
from app.db.models import Automation, User

class AdminActionsView(BaseView):
    name = "Экстренные Действия"
    category = "Система"
    icon = "fa-solid fa-bolt"
    
    @expose("/admin/actions", methods=["GET", "POST"])
    async def actions_page(self, request: Request):
        if request.method == "POST":
            form = await request.form()
            session = request.state.session
            message = ""
            
            if "panic_button" in form:
                arq_pool = request.app.state.arq_pool
                all_jobs = await arq_pool.all_jobs()
                aborted_count = 0
                for job in all_jobs:
                    try:
                        await arq_pool.abort_job(job.job_id)
                        aborted_count += 1
                    except Exception:
                        pass
                
                await session.execute(update(Automation).values(is_active=False))
                await session.execute(update(User).values(is_frozen=True))
                await session.commit()
                message = f"РЕЖИМ ПАНИКИ АКТИВИРОВАН: Отменено {aborted_count} задач, все автоматизации и пользователи заморожены."
            
            return self.templates.TemplateResponse("admin/actions.html", {"request": request, "message": message})
        
        return self.templates.TemplateResponse("admin/actions.html", {"request": request})