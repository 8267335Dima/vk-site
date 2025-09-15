# backend/tests/test_complex_scenarios.py
import pytest
import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, update

from app.db.models import User, Notification
from tests.utils.task_runner import run_and_verify_task, run_worker_for_duration
from app.tasks.cron_jobs import check_expired_plans_job # Импортируем саму cron-задачу

pytestmark = pytest.mark.asyncio

async def test_chain_of_tasks_respects_limits(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    Сложный сценарий:
    1. Устанавливаем пользователю низкий лимит лайков (15).
    2. Запускаем задачу "Лайки в ленте", которая ставит 10 лайков.
    3. Сразу после нее запускаем "Добавить друзей" (2 чел) с опцией "лайкать аватар".
    4. Проверяем, что обе задачи выполнились успешно, и общее число лайков не превысило лимит.
    """
    print("\n--- Комплексный тест: Цепочка задач и общий лимит ---")
    user, headers = authorized_user_and_headers
    
    # 1. Установка низкого лимита
    original_limit = user.daily_likes_limit
    user.daily_likes_limit = 15
    db_session.add(user)
    await db_session.commit()
    print(f"[SETUP] Временно установлен лимит в {user.daily_likes_limit} лайков.")

    try:
        # 2. Задача №1: Лайки в ленте
        print("\n[ACTION 1/2] Запуск 'Лайки в ленте' (10 штук)")
        like_payload = {"count": 10, "filters": {}}
        await run_and_verify_task(async_client, db_session, headers, "like_feed", like_payload, user.id)

        # 3. Задача №2: Добавление с лайком
        print("\n[ACTION 2/2] Запуск 'Добавить друзей' (2) с лайком аватара")
        add_payload = {
            "count": 2,
            "filters": {"allow_closed_profiles": False}, # Ищем открытые, чтобы можно было лайкнуть
            "like_config": {"enabled": True, "targets": ["avatar"]}
        }
        await run_and_verify_task(async_client, db_session, headers, "add_recommended", add_payload, user.id)

        # 4. Проверка
        await db_session.refresh(user, attribute_names=['daily_stats'])
        today_stats = next((s for s in user.daily_stats if s.date == datetime.date.today()), None)
        
        assert today_stats is not None, "Статистика за сегодня не найдена!"
        print(f"[VERIFY] Всего поставлено лайков за сегодня: {today_stats.likes_count}")
        assert today_stats.likes_count <= 15
        print("✓ Общий лимит лайков не был превышен в цепочке из двух задач.")

    finally:
        # Возвращаем лимит обратно
        user.daily_likes_limit = original_limit
        db_session.add(user)
        await db_session.commit()
        print("[CLEANUP] Исходный лимит лайков восстановлен.")


async def test_plan_expiration_flow(db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    Проверяет полный цикл истечения подписки:
    1. Устанавливаем пользователю дату истечения тарифа на "вчера".
    2. Запускаем cron-задачу, которая проверяет истекшие тарифы.
    3. Проверяем, что у пользователя сменился тариф на 'Expired',
       урезались лимиты и появилось системное уведомление.
    """
    print("\n--- Комплексный тест: Истечение срока действия тарифа ---")
    user, _ = authorized_user_and_headers
    
    # 1. Устанавливаем тариф на "вчера"
    user.plan = "PRO"
    user.plan_expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    db_session.add(user)
    await db_session.commit()
    print(f"[SETUP] Для пользователя {user.id} установлен тариф PRO, истекший вчера.")

    # 2. Запускаем cron-задачу
    print("[ACTION] Запуск cron-задачи check_expired_plans_job...")
    # Имитируем контекст, который ожидает ARQ
    await check_expired_plans_job(ctx={}) 
    print("[ACTION] ✓ Cron-задача отработала.")

    # 3. Проверяем результат
    await db_session.refresh(user)
    
    assert user.plan == "Expired", f"Тариф не сменился на Expired, текущий: {user.plan}"
    print(f"[VERIFY] ✓ Тариф пользователя успешно изменен на '{user.plan}'.")
    
    # Проверяем, что лимиты урезались до значений тарифа Expired
    from app.core.plans import get_limits_for_plan
    expired_limits = get_limits_for_plan("Expired")
    assert user.daily_likes_limit == expired_limits['daily_likes_limit']
    print(f"[VERIFY] ✓ Дневные лимиты урезаны до {user.daily_likes_limit} лайков.")

    # Проверяем наличие уведомления
    notification_stmt = select(Notification).where(
        Notification.user_id == user.id, 
        Notification.message.like("%Срок действия тарифа 'PRO' истек%")
    )
    notification = (await db_session.execute(notification_stmt)).scalar_one_or_none()
    assert notification is not None, "Системное уведомление об истечении тарифа не найдено!"
    print(f"[VERIFY] ✓ Найдено уведомление: '{notification.message}'")

    # Очистка
    user.plan_expires_at = None
    user.plan = "PRO"
    await db_session.execute(delete(Notification).where(Notification.id == notification.id))
    await db_session.commit()
    print("[CLEANUP] Пользователю возвращен PRO тариф, уведомление удалено.")