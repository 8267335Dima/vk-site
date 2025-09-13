# backend/app/core/constants.py
from enum import Enum

class PlanName(str, Enum):
    BASE = "Базовый"
    PLUS = "Plus"
    PRO = "PRO"
    AGENCY = "Agency"
    EXPIRED = "Expired"

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