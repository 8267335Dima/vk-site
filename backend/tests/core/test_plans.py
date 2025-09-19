# tests/core/test_plans.py

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.plans import is_feature_available_for_plan
from app.db.models import User
from app.core.enums import PlanName

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_user_factory():
    def _factory(is_admin: bool, plan_name: str):
        user = User(is_admin=is_admin)
        # ▼▼▼ ИЗМЕНЕНИЕ 2: Создаем mock-объект вместо строки ▼▼▼
        # SQLAlchemy ожидает объект, а не строку для поля-отношения
        mock_plan = MagicMock()
        mock_plan.name_id = plan_name
        user.plan = mock_plan
        return user
    return _factory

# Параметризованный тест для всех сценариев
@pytest.mark.parametrize(
    "user_is_admin, plan_name, feature_globally_enabled, expected_result",
    [
        # 1. Админ всегда имеет доступ, даже если фича выключена глобально
        (True, PlanName.BASE.name, False, True),
        (True, PlanName.EXPIRED.name, False, True),
        
        # 2. Если фича выключена глобально, никто (кроме админа) не имеет доступа
        (False, PlanName.PRO.name, False, False),
        (False, PlanName.BASE.name, False, False),
        
        # 3. Проверяем доступ по тарифу, когда фича включена глобально
        (False, PlanName.PRO.name, True, True),    # PRO имеет доступ ко всему ("*")
        (False, PlanName.PLUS.name, True, True),   # 'automations_center' доступен на PLUS
        (False, PlanName.BASE.name, True, False),  # 'automations_center' недоступен на BASE
        (False, PlanName.EXPIRED.name, True, False),# 'automations_center' недоступен на EXPIRED
    ]
)
async def test_is_feature_available_for_plan(
    mocker, mock_user_factory, user_is_admin, plan_name, feature_globally_enabled, expected_result
):
    """
    Тест проверяет логику доступа к фичам в зависимости от роли пользователя,
    тарифа и глобальных настроек.
    """
    # Arrange
    mocker.patch(
        'app.core.plans.SystemService.is_feature_enabled', 
        return_value=feature_globally_enabled
    )
    
    user = mock_user_factory(is_admin=user_is_admin, plan_name=plan_name)
    feature_id = "automations_center"

    # Act
    # ▼▼▼ ИЗМЕНЕНИЕ 3: Передаем в функцию строку plan_name, а не объект user.plan ▼▼▼
    result = await is_feature_available_for_plan(plan_name, feature_id, user=user)

    # Assert
    assert result == expected_result