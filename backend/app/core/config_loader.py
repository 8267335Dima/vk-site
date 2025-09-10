# backend/app/core/config_loader.py
import yaml
from pathlib import Path
from functools import lru_cache

# Определяем путь к директории с конфигами относительно текущего файла
CONFIG_PATH = Path(__file__).parent / "configs"

@lru_cache(maxsize=None)
def load_plans_config() -> dict:
    """Загружает и кеширует конфигурацию тарифных планов."""
    config_file = CONFIG_PATH / "plans.yml"
    if not config_file.is_file():
        raise FileNotFoundError("Configuration file for plans not found: plans.yml")
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

@lru_cache(maxsize=None)
def load_automations_config() -> list:
    """Загружает и кеширует конфигурацию типов автоматизаций."""
    config_file = CONFIG_PATH / "automations.yml"
    if not config_file.is_file():
        raise FileNotFoundError("Configuration file for automations not found: automations.yml")
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# Загружаем конфиги при старте модуля, чтобы проверить их наличие
try:
    PLAN_CONFIG = load_plans_config()
    AUTOMATIONS_CONFIG = load_automations_config()
except FileNotFoundError as e:
    print(f"CRITICAL ERROR: {e}")
    # В реальном приложении здесь можно остановить запуск
    exit(1)