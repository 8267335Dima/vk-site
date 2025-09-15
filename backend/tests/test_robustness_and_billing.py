import pytest
import datetime
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.db.models import User, Automation, TaskHistory, DailyStats, Payment
from app.core.constants import PlanName
from app.core.security import encrypt_data
from backend.tests.conftest import db_session
from tests.utils.task_runner import run_and_verify_task

pytestmark = pytest.mark.asyncio

# === ТЕСТЫ ЛИМИТОВ И ПАРАЛЛЕЛЬНОЙ РАБОТЫ ===

async def test_task_stops_gracefully_on_limit_breach(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    Сценарий: Пользователь хочет добавить 20 друзей, но его дневной лимит - всего 5.
    Система должна добавить 5 друзей и завершить задачу с ошибкой о превышении лимита.
    """
    print("\n--- Тест на устойчивость: Превышение лимита в процессе выполнения ---")
    user, headers = authorized_user_and_headers
    
    original_limit = user.daily_add_friends_limit
    user.daily_add_friends_limit = 5
    await db_session.commit()
    print(f"[SETUP] Временно установлен лимит в {user.daily_add_friends_limit} заявок в друзья.")

    try:
        payload = {"count": 20, "filters": {"allow_closed_profiles": True}}
        
        # Запускаем задачу, ожидаем, что она завершится с ошибкой
        response = await async_client.post("/api/v1/tasks/run/add_recommended", headers=headers, json=payload)
        assert response.status_code == 200
        job_id = response.json()['task_id']
        
        # Запускаем воркер для выполнения
        from app.worker import Worker, WorkerSettings
        worker = Worker(functions=WorkerSettings.functions, redis_settings=WorkerSettings.redis_settings, burst=True, poll_delay=0)
        await worker.main()

        # Проверяем результат
        db_session.expire_all()
        task = await db_session.scalar(select(TaskHistory).where(TaskHistory.celery_task_id == job_id))
        
        assert task.status == "FAILURE", "Задача должна была упасть с ошибкой лимита, но завершилась успешно."
        assert "Достигнут дневной лимит" in task.result
        print(f"✓ Задача корректно завершилась с ошибкой: '{task.result}'")
        
        today_stats = await db_session.scalar(select(DailyStats).where(DailyStats.user_id == user.id, DailyStats.date == datetime.date.today()))
        assert today_stats.friends_added_count == 5
        print(f"✓ Проверка БД: было отправлено ровно {today_stats.friends_added_count} заявок, как и требовал лимит.")

    finally:
        user.daily_add_friends_limit = original_limit
        await db_session.commit()
        print("[CLEANUP] Исходный лимит заявок восстановлен.")


async def test_concurrency_limit(async_client: AsyncClient, authorized_user_and_headers: tuple):
    """
    Сценарий: У пользователя тариф Plus (3 одновременные задачи).
    Мы пытаемся запустить 4 долгие задачи. Первые 3 должны запуститься, четвертая - получить ошибку 429.
    """
    print("\n--- Тест на устойчивость: Лимит одновременных задач ---")
    user, headers = authorized_user_and_headers

    # Для этого теста нужно, чтобы у пользователя был тариф с известным лимитом
    assert user.plan == PlanName.PRO, "Этот тест требует PRO тарифа для предсказуемости лимитов"
    # Лимит PRO - 5 задач
    
    # Мы не можем запустить "долгую" задачу, но можем симулировать их наличие в БД
    active_tasks = [
        TaskHistory(user_id=user.id, task_name="Симуляция", status="PENDING"),
        TaskHistory(user_id=user.id, task_name="Симуляция", status="STARTED"),
        TaskHistory(user_id=user.id, task_name="Симуляция", status="STARTED"),
        TaskHistory(user_id=user.id, task_name="Симуляция", status="PENDING"),
        TaskHistory(user_id=user.id, task_name="Симуляция", status="STARTED"),
    ]
    db_session.add_all(active_tasks)
    await db_session.commit()
    print(f"[SETUP] В БД создано 5 'активных' задач.")

    try:
        # Пытаемся запустить 6-ю задачу
        payload = {"count": 1, "filters": {}}
        response = await async_client.post("/api/v1/tasks/run/like_feed", headers=headers, json=payload)
        
        assert response.status_code == 429, "Ожидалась ошибка 429, но получен другой статус"
        assert "Достигнут лимит на одновременное выполнение задач" in response.text
        print("✓ Получена ожидаемая ошибка 429 Too Many Requests при попытке превысить лимит.")
        
    finally:
        for task in active_tasks:
            await db_session.delete(task)
        await db_session.commit()
        print("[CLEANUP] Симуляционные задачи удалены.")


# === ТЕСТЫ ЛОГИКИ ТАРИФОВ И ОПЛАТЫ ===

async def test_plan_renewal_extends_correctly(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    Сценарий: У пользователя тариф истекает через 5 дней. Он покупает еще 1 месяц.
    Новая дата истечения должна быть 'сегодня + 5 дней + 1 месяц', а не 'сегодня + 1 месяц'.
    """
    print("\n--- Тест логики биллинга: Корректное продление тарифа ---")
    user, _ = authorized_user_and_headers
    
    # 1. Устанавливаем дату истечения в будущем
    future_expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)
    user.plan_expires_at = future_expiry
    await db_session.commit()
    print(f"[SETUP] Установлена дата истечения тарифа: {future_expiry.date()}")

    # 2. Симулируем успешную оплату через webhook
    plan_to_buy = PlanName.PRO
    months_to_buy = 1
    payment_amount = 1499.0
    
    # Создаем запись о платеже в БД, как это сделал бы эндпоинт create-payment
    payment = Payment(
        payment_system_id=f"test_payment_{uuid.uuid4()}",
        user_id=user.id,
        amount=payment_amount,
        status="pending",
        plan_name=plan_to_buy,
        months=months_to_buy
    )
    db_session.add(payment)
    await db_session.commit()
    
    webhook_payload = {
        "event": "payment.succeeded",
        "object": {
            "id": payment.payment_system_id,
            "status": "succeeded",
            "amount": {"value": str(payment_amount), "currency": "RUB"},
        }
    }
    
    print(f"[ACTION] Имитация вызова webhook для оплаты {months_to_buy} мес. тарифа {plan_to_buy}")
    response = await async_client.post("/api/v1/billing/webhook", json=webhook_payload)
    assert response.status_code == 200, "Webhook вернул ошибку"

    # 3. Проверяем новую дату
    await db_session.refresh(user)
    expected_expiry = future_expiry + datetime.timedelta(days=30 * months_to_buy)
    
    print(f"[VERIFY] Новая дата истечения в БД: {user.plan_expires_at.date()}")
    print(f"[VERIFY] Ожидаемая дата истечения:   {expected_expiry.date()}")
    
    assert user.plan_expires_at.date() == expected_expiry.date(), "Дата продления тарифа рассчитана неверно!"
    print("✓ Тариф продлен корректно, новая дата истечения отсчитана от предыдущей.")


# === ТЕСТЫ ОБРАБОТКИ КРИТИЧЕСКИХ ОШИБОК ===

async def test_invalid_vk_token_disables_automations(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    Сценарий: Токен VK пользователя становится невалидным.
    При попытке выполнить любую задачу, она должна упасть с ошибкой авторизации,
    а ВСЕ активные автоматизации этого пользователя должны быть отключены в БД.
    """
    print("\n--- Тест на отказ: Автоматическое отключение при невалидном токене VK ---")
    user, headers = authorized_user_and_headers
    
    # 1. Создаем и активируем фейковую автоматизацию
    automation = Automation(user_id=user.id, automation_type="like_feed", is_active=True)
    db_session.add(automation)
    await db_session.commit()
    print("[SETUP] Создана и активирована автоматизация 'Лайки в ленте'.")
    
    # 2. "Портим" токен в БД
    original_token = user.encrypted_vk_token
    user.encrypted_vk_token = encrypt_data("invalid_token_for_test")
    await db_session.commit()
    print("[SETUP] Токен VK в базе данных заменен на невалидный.")
    
    try:
        # 3. Пытаемся запустить задачу
        payload = {"count": 1, "filters": {}}
        response = await async_client.post("/api/v1/tasks/run/like_feed", headers=headers, json=payload)
        job_id = response.json()['task_id']
        
        from app.worker import Worker, WorkerSettings
        worker = Worker(functions=WorkerSettings.functions, redis_settings=WorkerSettings.redis_settings, burst=True, poll_delay=0)
        await worker.main()

        # 4. Проверяем результаты
        task = await db_session.scalar(select(TaskHistory).where(TaskHistory.celery_task_id == job_id))
        assert task.status == "FAILURE"
        assert "Ошибка авторизации VK" in task.result
        print("✓ Задача предсказуемо упала с ошибкой авторизации.")
        
        await db_session.refresh(automation)
        assert automation.is_active is False, "Автоматизация не была отключена после ошибки токена!"
        print("✓ Проверка БД: Все автоматизации пользователя были успешно деактивированы.")

    finally:
        user.encrypted_vk_token = original_token
        await db_session.delete(automation)
        await db_session.commit()
        print("[CLEANUP] Исходный токен VK и тестовая автоматизация восстановлены.")