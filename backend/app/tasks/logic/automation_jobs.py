# --- backend/app/tasks/logic/automation_jobs.py ---
# --- НОВАЯ ВЕРСИЯ ---
import datetime
import structlog
import pytz
import random
from redis.asyncio import Redis 
from sqlalchemy import String, select, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from arq.connections import ArqRedis
from app.core.enums import AutomationType
from app.db.models import Automation, TaskHistory, User
from app.core.config_loader import AUTOMATIONS_CONFIG, APP_SETTINGS # <-- ИЗМЕНЕНИЕ
log = structlog.get_logger(__name__)

log = structlog.get_logger(__name__)

TASK_FUNC_MAP_ARQ = {
    "accept_friends": "accept_friend_requests_task", "like_feed": "like_feed_task",
    "add_recommended": "add_recommended_friends_task", "view_stories": "view_stories_task",
    "remove_friends": "remove_friends_by_criteria_task", "mass_messaging": "mass_messaging_task",
    "join_groups": "join_groups_by_criteria_task", "leave_groups": "leave_groups_by_criteria_task",
    "birthday_congratulation": "birthday_congratulation_task", "eternal_online": "eternal_online_task",
}

async def _create_and_run_arq_task(session: AsyncSession, arq_pool: ArqRedis, user_id: int, task_name_key: str, settings_dict: dict):
    task_func_name = TASK_FUNC_MAP_ARQ.get(task_name_key)
    if not task_func_name:
        log.warn("cron.arq_task_not_found", task_name=task_name_key)
        return

    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_name_key), None)
    display_name = task_config.name if task_config else "Автоматическая задача"

    task_history = TaskHistory(user_id=user_id, task_name=display_name, status="PENDING", parameters=settings_dict)
    session.add(task_history)
    await session.flush()

    job = await arq_pool.enqueue_job(task_func_name, task_history_id=task_history.id, **(settings_dict or {}))
    task_history.arq_job_id = job.job_id

async def _run_daily_automations_async(session: AsyncSession, arq_pool: ArqRedis, automation_group: str):
    now_utc = datetime.datetime.now(pytz.utc)
    moscow_tz = pytz.timezone("Europe/Moscow")
    now_moscow = now_utc.astimezone(moscow_tz)

    automation_ids = [item.id for item in AUTOMATIONS_CONFIG if item.group == automation_group]
    if not automation_ids:
        return

    stmt = select(Automation).join(User).where(
        Automation.is_active == True,
        # Сравниваем напрямую с Enum объектами
        Automation.automation_type.in_([AutomationType(aid) for aid in automation_ids]),
        or_(User.plan_expires_at.is_(None), User.plan_expires_at > now_utc)
    ).options(selectinload(Automation.user))
    
    automations = (await session.execute(stmt)).scalars().unique().all()
    if not automations:
        return
        
    log.info("run_daily_automations.start", count=len(automations), group=automation_group)

    for automation in automations:
        if automation.automation_type == 'eternal_online':
            automation_settings = automation.settings or {}
            if automation_settings.get('mode', 'schedule') == 'schedule':
                day_key = str(now_moscow.isoweekday())
                day_schedule = automation_settings.get('schedule_weekly', {}).get(day_key)

                if not day_schedule or not day_schedule.get('is_active'):
                    continue

                try:
                    start = datetime.datetime.strptime(day_schedule.get('start_time', '00:00'), '%H:%M').time()
                    end = datetime.datetime.strptime(day_schedule.get('end_time', '23:59'), '%H:%M').time()
                    
                    if not (start <= now_moscow.time() <= end):
                        continue
                    
                    if automation_settings.get('humanize', True) and random.random() < APP_SETTINGS.cron.humanize_online_skip_chance: # <-- ИЗМЕНЕНИЕ
                        log.info("eternal_online.humanizer_skip", user_id=automation.user_id)
                        continue
                except (ValueError, TypeError) as e:
                    # Эта ошибка теперь не должна возникать, но оставим защиту
                    log.error("eternal_online.schedule_parse_error", user_id=automation.user_id, schedule=day_schedule, error=str(e))
                    continue
        
        automation.last_run_at = now_utc
        # Используем вложенную транзакцию для атомарного создания задачи
        async with session.begin_nested():
            await _create_and_run_arq_task(session, arq_pool, automation.user_id, automation.automation_type, automation.settings)