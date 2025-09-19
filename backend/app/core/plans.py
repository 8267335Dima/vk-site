# backend/app/core/plans.py

from functools import lru_cache
# --- ДОБАВЬТЕ ЭТИ ИМПОРТЫ ---
from typing import Optional
from app.db.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config_loader import PLAN_CONFIG, AUTOMATIONS_CONFIG
from app.core.enums import PlanName, FeatureKey
from app.services.system_service import SystemService # <--- ДОБАВЬТЕ ЭТОТ ИМПОРТ


@lru_cache(maxsize=16)
def get_plan_config(plan_name: PlanName | str) -> dict:
    key = plan_name.name if isinstance(plan_name, PlanName) else plan_name
    plan_model = PLAN_CONFIG.get(key, PLAN_CONFIG["EXPIRED"])
    return plan_model.model_dump()


def get_limits_for_plan(plan_name: PlanName | str) -> dict:
    """Возвращает словарь с лимитами для указанного плана."""
    plan_data = get_plan_config(plan_name)
    return plan_data.get("limits", {}).copy()


@lru_cache(maxsize=1)
def get_all_feature_keys() -> list[str]:
    """Возвращает список всех возможных ключей фич из конфига."""
    automation_ids = [item.id for item in AUTOMATIONS_CONFIG]

    other_features = [
        FeatureKey.PROXY_MANAGEMENT,
        FeatureKey.SCENARIOS,
        FeatureKey.PROFILE_GROWTH_ANALYTICS,
        FeatureKey.FAST_SLOW_DELAY_PROFILE,
        FeatureKey.AUTOMATIONS_CENTER,
        FeatureKey.AGENCY_MODE,
        FeatureKey.POST_SCHEDULER,
    ]
    return list(set(automation_ids + [f.value for f in other_features]))


async def is_feature_available_for_plan(
    plan_name: PlanName | str,
    feature_id: str,
    db: AsyncSession, # <--- ПРИНИМАЕТ СЕССИЮ
    user: Optional[User] = None
    ) -> bool:
    """
    Проверяет, доступна ли фича для тарифа, с учетом глобальных настроек и прав администратора.
    """
    if user and user.is_admin:
        return True
    # --- ИСПРАВЛЕНИЕ: передаем сессию дальше ---
    if not await SystemService.is_feature_enabled(feature_id, session=db):
        return False

    key = plan_name if isinstance(plan_name, str) else plan_name.name_id
    plan_model = PLAN_CONFIG.get(key, PLAN_CONFIG[PlanName.EXPIRED.name])

    available_features = plan_model.available_features

    if available_features == "*":
        return True

    return feature_id in available_features


def get_features_for_plan(plan_name: PlanName | str) -> list[str]:
    """
    Возвращает полный список доступных ключей фич для тарифного плана.
    Обрабатывает wildcard '*' для PRO тарифов.
    """
    key = plan_name if isinstance(plan_name, str) else plan_name.name_id
    plan_model = PLAN_CONFIG.get(key, PLAN_CONFIG[PlanName.EXPIRED.name])
    available = plan_model.available_features
    
    if available == "*":
        return get_all_feature_keys()
    
    return available if isinstance(available, list) else []