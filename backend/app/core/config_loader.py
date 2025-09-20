# backend/app/core/config_loader.py
import yaml
from pathlib import Path
from functools import lru_cache
from app.core.schemas.config import AppSettings, PlanConfig, AutomationConfig

# Определяем путь к директории с конфигами относительно текущего файла
CONFIG_PATH = Path(__file__).parent / "configs"

@lru_cache(maxsize=1)
def load_app_settings_config() -> AppSettings:
    config_file = CONFIG_PATH / "app_settings.yml"
    if not config_file.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)
    return AppSettings(**raw_config)


@lru_cache(maxsize=1)
def load_plans_config() -> dict[str, PlanConfig]:
    """
    Загружает, валидирует через Pydantic и кеширует конфигурацию тарифных планов.
    Возвращает словарь, где ключ - ID тарифа, значение - Pydantic модель.
    """
    config_file = CONFIG_PATH / "plans.yml"
    if not config_file.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)
    
    return {plan_id: PlanConfig(**data) for plan_id, data in raw_config.items()}

@lru_cache(maxsize=1)
def load_automations_config() -> list[AutomationConfig]:
    """
    Загружает, валидирует через Pydantic и кеширует конфигурацию типов автоматизаций.
    """
    config_file = CONFIG_PATH / "automations.yml"
    if not config_file.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)
        
    return [AutomationConfig(**item) for item in raw_config]

# Загружаем конфиги при старте модуля, чтобы проверить их наличие и валидность
try:
    PLAN_CONFIG = load_plans_config()
    AUTOMATIONS_CONFIG = load_automations_config()
    APP_SETTINGS = load_app_settings_config()
except (FileNotFoundError, Exception) as e:
    print(f"CRITICAL ERROR loading configs: {e}")
    exit(1)