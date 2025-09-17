# backend/app/core/constants.py
from enum import Enum

class PlanName(str, Enum):
    BASE = "BASE"
    PLUS = "PLUS"
    PRO = "PRO"
    AGENCY = "AGENCY"
    EXPIRED = "EXPIRED"

class FeatureKey(str, Enum):
    PROXY_MANAGEMENT = "proxy_management"
    SCENARIOS = "scenarios"
    PROFILE_GROWTH_ANALYTICS = "profile_growth_analytics"
    FAST_SLOW_DELAY_PROFILE = "fast_slow_delay_profile"
    AUTOMATIONS_CENTER = "automations_center"
    AGENCY_MODE = "agency_mode"
    POST_SCHEDULER = "post_scheduler"

class TaskKey(str, Enum):
    ACCEPT_FRIENDS = "accept_friends"
    LIKE_FEED = "like_feed"
    ADD_RECOMMENDED = "add_recommended"
    VIEW_STORIES = "view_stories"
    REMOVE_FRIENDS = "remove_friends"
    MASS_MESSAGING = "mass_messaging"
    LEAVE_GROUPS = "leave_groups"
    JOIN_GROUPS = "join_groups"
    BIRTHDAY_CONGRATULATION = "birthday_congratulation"
    ETERNAL_ONLINE = "eternal_online"

class AutomationGroup(str, Enum):
    STANDARD = "standard"
    ONLINE = "online"
    CONTENT = "content"

class CronSettings:
    # Время в секундах, на которое блокируется запуск однотипных cron-задач,
    # чтобы избежать двойного выполнения при высокой нагрузке. 4 минуты.
    AUTOMATION_JOB_LOCK_EXPIRATION_SECONDS: int = 240

    # Шанс (от 0.0 до 1.0), с которым "Интеллектуальное присутствие"
    # пропустит 10-минутный цикл для имитации человеческого перерыва.
    HUMANIZE_ONLINE_SKIP_CHANCE: float = 0.15

    # Записи в истории задач старше этого количества дней будут удалены для PRO/Agency тарифов.
    TASK_HISTORY_RETENTION_DAYS_PRO: int = 90

    # Записи в истории задач старше этого количества дней будут удалены для бесплатных тарифов.
    TASK_HISTORY_RETENTION_DAYS_BASE: int = 30