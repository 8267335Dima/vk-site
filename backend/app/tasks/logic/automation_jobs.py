# --- backend/app/tasks/logic/automation_jobs.py ---
import datetime
import structlog
import pytz
import random
from redis.asyncio import Redis
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

# --- ИСПРАВЛЕНИЕ: Добавляем недостающий импорт ---
from app.core.config import settings
# -----------------------------------------------

from app.db.session import AsyncSessionFactory
from app.db.models import Automation, TaskHistory, User
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.core.constants import CronSettings

log = structlog.get_logger(__name__)

# Эта карта нужна для постановки ARQ задач из этого модуля
TASK_FUNC_MAP_ARQ = {
    "accept_friends": "accept_friend_requests_task", "like_feed": "like_feed_task",
    "add_recommended": "add_recommended_friends_task", "view_stories": "view_stories_task",
    "remove_friends": "remove_friends_by_criteria_task", "mass_messaging": "mass_messaging_task",
    "join_groups": "join_groups_by_criteria_task", "leave_groups": "leave_groups_by_criteria_task",
    "birthday_congratulation": "birthday_congratulation_task", "eternal_online": "eternal_online_task",
}

async def _create_and_run_arq_task(session, arq_pool, user_id, task_name_key, settings_dict):
    """Вспомогательная функция для создания TaskHistory и постановки задачи в ARQ."""
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
    task_history.celery_task_id = job.job_id
    await session.commit()

async def _run_daily_automations_async(automation_group: str):
    """
    Основная логика для запуска автоматизаций. Находит все активные автоматизации
    в указанной группе, проверяет их расписание и ставит в очередь ARQ.
    """
    from app.worker import redis_settings
    from arq.connections import create_pool

    redis_lock_client = await Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
    lock_key = f"lock:task:run_automations:{automation_group}"

    lock_acquired = await redis_lock_client.set(lock_key, "1", ex=CronSettings.AUTOMATION_JOB_LOCK_EXPIRATION_SECONDS, nx=True)
    if not lock_acquired:
        log.warn("run_daily_automations.already_running", group=automation_group)
        await redis_lock_client.close()
        return

    arq_pool = await create_pool(redis_settings)
    try:
        async with AsyncSessionFactory() as session:
            now_utc = datetime.datetime.now(pytz.utc)
            moscow_tz = pytz.timezone("Europe/Moscow")
            now_moscow = now_utc.astimezone(moscow_tz)

            automation_ids = [item.id for item in AUTOMATIONS_CONFIG if item.group == automation_group]
            if not automation_ids:
                return

            stmt = select(Automation).join(User).where(
                Automation.is_active == True,
                Automation.automation_type.in_(automation_ids),
                or_(User.plan_expires_at.is_(None), User.plan_expires_at > now_utc)
            ).options(selectinload(Automation.user))
            
            automations = (await session.execute(stmt)).scalars().unique().all()
            if not automations:
                return
                
            log.info("run_daily_automations.start", count=len(automations), group=automation_group)

            for automation in automations:
                if automation.automation_type == 'eternal_online':
                    automation_settings = automation.settings or {} # Используем другую переменную, чтобы не конфликтовать с глобальным `settings`
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
                            log.warn("eternal_online.invalid_time_format", user_id=automation.user_id, schedule=day_schedule)
                            continue
                
                automation.last_run_at = now_utc
                await _create_and_run_arq_task(session, arq_pool, automation.user_id, automation.automation_type, automation.settings)

    finally:
        await redis_lock_client.delete(lock_key)
        await redis_lock_client.close()
        await arq_pool.close()