# backend/app/tasks/logic/automation_jobs.py
import datetime
import structlog
import pytz
import random
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from arq.connections import ArqRedis

from app.db.models import Automation, TaskHistory, User
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.core.constants import CronSettings
from app.core.enums import TaskKey, AutomationType
from app.tasks.task_maps import TASK_FUNC_MAP

log = structlog.get_logger(__name__)



async def _create_and_run_arq_task(session: AsyncSession, arq_pool: ArqRedis, user_id: int, task_name_key: str, settings_dict: dict):
    try:
        task_key_enum = TaskKey(task_name_key)
        task_func_name = TASK_FUNC_MAP.get(task_key_enum)
    except ValueError:
        log.warn("cron.invalid_task_key", task_name=task_name_key)
        return

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
        
    automation_enums = [AutomationType(aid) for aid in automation_ids]

    stmt = select(Automation).join(User).where(
        Automation.is_active == True,
        Automation.automation_type.in_(automation_enums),
        or_(User.plan_expires_at.is_(None), User.plan_expires_at > now_utc)
    ).options(selectinload(Automation.user))
    
    automations = (await session.execute(stmt)).scalars().unique().all()
    if not automations:
        return
        
    log.info("run_daily_automations.start", count=len(automations), group=automation_group)

    for automation in automations:
        automation_type_value = automation.automation_type.value

        if automation_type_value == 'eternal_online':
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
                    
                    if automation_settings.get('humanize', True) and random.random() < CronSettings.HUMANIZE_ONLINE_SKIP_CHANCE:
                        log.info("eternal_online.humanizer_skip", user_id=automation.user_id)
                        continue
                except (ValueError, TypeError):
                    log.error("eternal_online.schedule_parse_error", user_id=automation.user_id, schedule=day_schedule)
                    continue
        
        automation.last_run_at = now_utc
        async with session.begin_nested():
            await _create_and_run_arq_task(session, arq_pool, automation.user_id, automation_type_value, automation.settings)