import enum

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