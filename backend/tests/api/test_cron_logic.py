# tests/api/test_cron_logic.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, UTC

# Импортируем модели и Enum
from app.db.models import User, Automation, Notification, Plan
from app.core.enums import PlanName
from app.tasks.logic.maintenance_jobs import _check_expired_plans_async

pytestmark = pytest.mark.asyncio


async def test_check_expired_plans_logic(db_session: AsyncSession):
    """
    Тестирует логику проверки истекших подписок.
    """
    # Arrange:
    # --- ИСПРАВЛЕНИЕ: Сначала получаем объект Plan из БД ---
    pro_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PRO.name))).scalar_one()
    expired_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.EXPIRED.name))).scalar_one()
    
    # --- ИСПРАВЛЕНИЕ: Используем plan_id для создания пользователей ---
    # 1. Пользователь с активной подпиской
    active_user = User(vk_id=1, encrypted_vk_token="active", plan_id=pro_plan.id, plan_expires_at=datetime.now(UTC) + timedelta(days=10))
    # 2. Пользователь, чья подписка истекла вчера
    expired_user = User(vk_id=2, encrypted_vk_token="expired", plan_id=pro_plan.id, plan_expires_at=datetime.now(UTC) - timedelta(days=1))
    # 3. Пользователь с вечной подпиской (админ)
    eternal_user = User(vk_id=3, encrypted_vk_token="eternal", plan_id=pro_plan.id, plan_expires_at=None)

    # Добавляем активную автоматизацию для пользователя, который должен "слететь"
    automation = Automation(user=expired_user, automation_type="like_feed", is_active=True)

    db_session.add_all([active_user, expired_user, eternal_user, automation])
    await db_session.commit()

    # Act: Вызываем тестируемую функцию
    await _check_expired_plans_async(session=db_session)

    # Assert:
    # Обновляем состояние объектов из БД, чтобы увидеть изменения
    await db_session.refresh(active_user, ['plan'])
    await db_session.refresh(expired_user, ['plan'])
    await db_session.refresh(eternal_user, ['plan'])
    await db_session.refresh(automation)

    # 1. План активного пользователя не изменился
    assert active_user.plan.name_id == PlanName.PRO.name

    # 2. План пользователя с истекшей подпиской изменился на EXPIRED
    assert expired_user.plan.name_id == PlanName.EXPIRED.name
    # Его автоматизация была деактивирована
    assert automation.is_active is False

    # 3. План админа не изменился
    assert eternal_user.plan.name_id == PlanName.PRO.name

    # 4. Проверяем, что было создано уведомление для "слетевшего" пользователя
    notification = (await db_session.execute(
        select(Notification).where(Notification.user_id == expired_user.id)
    )).scalar_one_or_none()
    
    assert notification is not None
    assert "истек" in notification.message