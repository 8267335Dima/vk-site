# tests/db/test_cascades_db.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.models import User, TaskHistory, Automation, FilterPreset, Proxy, Notification, Scenario, Plan
from app.core.enums import PlanName

pytestmark = pytest.mark.asyncio

async def test_user_deletion_cascades(db_session: AsyncSession):
    """
    Тест проверяет, что при удалении пользователя (User) происходит
    каскадное удаление всех связанных с ним данных.
    """
    # Arrange: Создаем пользователя и полный набор связанных с ним сущностей
    pro_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PRO.name))).scalar_one()
    
    user_to_delete = User(
        vk_id=999,
        encrypted_vk_token="token_to_delete",
        plan_id=pro_plan.id
    )
    db_session.add(user_to_delete)
    await db_session.flush()
    
    related_entities = [
        TaskHistory(user_id=user_to_delete.id, task_name="Test Task"),
        Automation(user_id=user_to_delete.id, automation_type="like_feed"),
        FilterPreset(user_id=user_to_delete.id, name="Test Preset", action_type="some_action", filters={}),
        Proxy(user_id=user_to_delete.id, encrypted_proxy_url="encrypted_url"),
        Notification(user_id=user_to_delete.id, message="Test Notification"),
        Scenario(user_id=user_to_delete.id, name="Test Scenario", schedule="* * * * *")
    ]
    db_session.add_all(related_entities)
    await db_session.commit()

    # Act: Удаляем пользователя
    await db_session.delete(user_to_delete)
    await db_session.commit()

    # Assert: Проверяем, что все связанные записи были удалены
    assert (await db_session.get(User, user_to_delete.id)) is None
    
    related_models = [TaskHistory, Automation, FilterPreset, Proxy, Notification, Scenario]
    for model in related_models:
        count = (await db_session.execute(select(func.count(model.id)))).scalar_one()
        assert count == 0, f"Таблица {model.__tablename__} не была очищена после удаления пользователя!"