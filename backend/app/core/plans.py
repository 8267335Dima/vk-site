# backend/app/core/plans.py
from functools import lru_cache
from app.core.config_loader import PLAN_CONFIG, AUTOMATIONS_CONFIG
from app.core.enums import PlanName, FeatureKey

@lru_cache(maxsize=16)
def get_plan_config(plan_name: PlanName | str) -> dict:
    # Эта функция теперь будет корректно работать, т.к. user.plan
    # будет хранить системное имя ("BASE", "PRO" и т.д.)
    key = plan_name.name if isinstance(plan_name, PlanName) else plan_name
    plan_model = PLAN_CONFIG.get(key, PLAN_CONFIG["EXPIRED"]) # Используем строковый ключ "EXPIRED"
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
    # ИЗМЕНЕНО: Ключевое исправление.
    # Мы используем .name для получения строкового ключа, чтобы избежать KeyError.
    key = plan_name if isinstance(plan_name, str) else plan_name.name
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
    # ИЗМЕНЕНО: Аналогичное исправление для консистентности.
    key = plan_name if isinstance(plan_name, str) else plan_name.name
    plan_model = PLAN_CONFIG.get(key, PLAN_CONFIG[PlanName.EXPIRED.name])
    available = plan_model.available_features
    
    if available == "*":
        return get_all_feature_keys()
    
    return available if isinstance(available, list) else [] 