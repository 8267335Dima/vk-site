# backend/app/core/enums.py
import enum

class PlanName(str, enum.Enum):
    BASE = "BASE"
    PLUS = "PLUS"
    PRO = "PRO"
    AGENCY = "AGENCY"
    EXPIRED = "EXPIRED"

class FeatureKey(str, enum.Enum):
    PROXY_MANAGEMENT = "proxy_management"
    SCENARIOS = "scenarios"
    PROFILE_GROWTH_ANALYTICS = "profile_growth_analytics"
    FAST_SLOW_DELAY_PROFILE = "fast_slow_delay_profile"
    AUTOMATIONS_CENTER = "automations_center"
    AGENCY_MODE = "agency_mode"
    POST_SCHEDULER = "post_scheduler"
    AI_AUTO_RESPONDER = "ai_auto_responder"
    PARSE_GROUP_AUDIENCE = "parse_group_audience"
    EXPORT_CONVERSATION = "export_conversation"
    GROUP_ACTIONS = "group_actions"

class TaskKey(str, enum.Enum):
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
    AI_AUTO_RESPONDER = "ai_auto_responder"
    PARSE_GROUP_AUDIENCE = "parse_group_audience"
    EXPORT_CONVERSATION = "export_conversation"

class AutomationType(str, enum.Enum):
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

class ActionType(str, enum.Enum):
    LIKE_FEED = "like_feed"
    ADD_FRIENDS = "add_recommended"
    ACCEPT_FRIENDS = "accept_friends"
    REMOVE_FRIENDS = "remove_friends"
    VIEW_STORIES = "view_stories"
    BIRTHDAY_CONGRATULATION = "birthday_congratulation"
    MASS_MESSAGING = "mass_messaging"
    ETERNAL_ONLINE = "eternal_online"
    LEAVE_GROUPS = "leave_groups"
    JOIN_GROUPS = "join_groups"
    SYSTEM_NOTIFICATION = "system_notification"

class ActionStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"
    INFO = "info"

class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class DelayProfile(enum.Enum):
    slow = "slow"
    normal = "normal"
    fast = "fast"

class TeamMemberRole(enum.Enum):
    admin = "admin"
    member = "member"

class ScenarioStepType(enum.Enum):
    action = "action"
    condition = "condition"

class ScheduledPostStatus(enum.Enum):
    scheduled = "scheduled"
    published = "published"
    failed = "failed"

class FriendRequestStatus(enum.Enum):
    pending = "pending"
    accepted = "accepted"