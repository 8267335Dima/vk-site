# backend/tests/test_messaging_tasks.py
import pytest
import datetime
import random
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User
from app.services.vk_api import VKAPI
from tests.utils.task_runner import run_and_verify_task

pytestmark = pytest.mark.asyncio

async def test_real_mass_messaging_to_friends(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    """
    Тест отправляет 2 РЕАЛЬНЫХ сообщения двум случайным друзьям,
    которые сейчас онлайн.
    """
    user, headers = authorized_user_and_headers
    
    # Находим цели
    friends = await vk_api_client.get_user_friends(user.vk_id, fields="online")
    online_friends = [f for f in friends['items'] if f.get('online')]
    
    message_count = 2
    assert len(online_friends) >= message_count, f"Для теста нужно как минимум {message_count} друга онлайн."
    
    targets = random.sample(online_friends, message_count)
    target_names = [f"{t['first_name']} {t['last_name']}" for t in targets]
    print(f"[PREP] Выбраны реальные цели для рассылки: {', '.join(target_names)}")
    
    # Запускаем задачу
    message = f"🤖 Привет! Это автоматическое тестовое сообщение от Pytest {int(datetime.datetime.utcnow().timestamp())}. Не обращай внимания."
    payload = {
        "count": message_count, 
        "message_text": message,
        "filters": {"is_online": True, "allow_closed_profiles": True}
    }
    
    task_result = await run_and_verify_task(async_client, db_session, headers, "mass_messaging", payload, user.id)
    print("✓ Задача рассылки завершилась успешно. Проверьте ваши диалоги в VK.")