# backend/app/core/constants.py

# Этот файл содержит классы-контейнеры для констант и настроек.
# Все перечисления (Enums) были вынесены в `app/core/enums.py`.

class CronSettings:
    AUTOMATION_JOB_LOCK_EXPIRATION_SECONDS: int = 240
    HUMANIZE_ONLINE_SKIP_CHANCE: float = 0.15
    TASK_HISTORY_RETENTION_DAYS_PRO: int = 90
    TASK_HISTORY_RETENTION_DAYS_BASE: int = 30