# backend/app/core/plans.py
from app.core.config_loader import PLAN_CONFIG, AUTOMATIONS_CONFIG

def get_plan_config(plan_name: str) -> dict:
    """Безопасно получает конфигурацию плана, возвращая 'Expired' если план не найден."""
    return PLAN_CONFIG.get(plan_name, PLAN_CONFIG["Expired"])

def get_limits_for_plan(plan_name: str) -> dict:
    """Возвращает словарь с лимитами для указанного плана."""
    plan_data = get_plan_config(plan_name)
    return plan_data.get("limits", {}).copy()

def is_automation_available_for_plan(plan_name: str, automation_id: str) -> bool:
    """Проверяет, доступна ли указанная автоматизация для данного тарифного плана."""
    plan_data = get_plan_config(plan_name)
    available = plan_data.get("available_automations", [])
    
    if available == "*":
        return True
    
    return automation_id in available

# --- НОВАЯ ФУНКЦИЯ ---
def is_feature_available_for_plan(plan_name: str, feature_id: str) -> bool:
    """Проверяет, доступна ли указанная премиум-функция для данного тарифного плана."""
    plan_data = get_plan_config(plan_name)
    available_features = plan_data.get("available_features", [])
    return feature_id in available_features