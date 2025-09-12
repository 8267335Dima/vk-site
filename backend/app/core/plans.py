# backend/app/core/plans.py
from app.core.config_loader import PLAN_CONFIG, AUTOMATIONS_CONFIG

def get_plan_config(plan_name: str) -> dict:
    """Безопасно получает конфигурацию плана, возвращая 'Expired' если план не найден."""
    return PLAN_CONFIG.get(plan_name, PLAN_CONFIG.get("Expired", {}))

def get_limits_for_plan(plan_name: str) -> dict:
    """Возвращает словарь с лимитами для указанного плана."""
    plan_data = get_plan_config(plan_name)
    return plan_data.get("limits", {}).copy()

def get_all_feature_keys() -> list[str]:
    """Возвращает список всех возможных ключей фич из конфига."""
    automation_ids = [item.get('id') for item in AUTOMATIONS_CONFIG if item.get('id')]
    # --- ИСПРАВЛЕНИЕ: Добавляем 'automations_center' в список всех фич ---
    other_features = [
        'proxy_management', 
        'scenarios', 
        'profile_growth_analytics', 
        'fast_slow_delay_profile',
        'automations_center'
    ]
    return list(set(automation_ids + other_features))

def is_feature_available_for_plan(plan_name: str, feature_id: str) -> bool:
    """Проверяет, доступна ли указанная фича для данного тарифного плана."""
    plan_data = get_plan_config(plan_name)
    available_features = plan_data.get("available_features", [])
    
    if available_features == "*":
        return True
    
    return feature_id in available_features

def get_features_for_plan(plan_name: str) -> list[str]:
    """
    Возвращает полный список доступных ключей фич для тарифного плана.
    Обрабатывает wildcard '*' для PRO тарифов.
    """
    plan_data = get_plan_config(plan_name)
    available = plan_data.get("available_features", [])
    
    if available == "*":
        return get_all_feature_keys() # Если '*', возвращаем все возможные фичи
    
    return available if isinstance(available, list) else []