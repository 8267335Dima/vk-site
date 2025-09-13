# backend/app/core/plans.py
from functools import lru_cache
from app.core.config_loader import PLAN_CONFIG, AUTOMATIONS_CONFIG
from app.core.constants import PlanName, FeatureKey, TaskKey

@lru_cache(maxsize=16)
def get_plan_config(plan_name: PlanName | str) -> dict:
    """Безопасно получает конфигурацию плана, возвращая 'Expired' если план не найден."""
    plan_model = PLAN_CONFIG.get(str(plan_name), PLAN_CONFIG[PlanName.EXPIRED])
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

@lru_cache(maxsize=256)
def is_feature_available_for_plan(plan_name: PlanName | str, feature_id: str) -> bool:
    """Проверяет, доступна ли указанная фича для данного тарифного плана."""
    plan_model = PLAN_CONFIG.get(str(plan_name), PLAN_CONFIG[PlanName.EXPIRED])
    available_features = plan_model.available_features
    
    if available_features == "*":
        return True
    
    return feature_id in available_features

def get_features_for_plan(plan_name: PlanName | str) -> list[str]:
    """
    Возвращает полный список доступных ключей фич для тарифного плана.
    Обрабатывает wildcard '*' для PRO тарифов.
    """
    plan_model = PLAN_CONFIG.get(str(plan_name), PLAN_CONFIG[PlanName.EXPIRED])
    available = plan_model.available_features
    
    if available == "*":
        return get_all_feature_keys()
    
    return available if isinstance(available, list) else []