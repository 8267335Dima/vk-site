from app.services.feed_service import FeedService
from app.services.incoming_request_service import IncomingRequestService
from app.services.outgoing_request_service import OutgoingRequestService
from app.services.friend_management_service import FriendManagementService
from app.services.story_service import StoryService
from app.services.automation_service import AutomationService
from app.services.message_service import MessageService
from app.services.group_management_service import GroupManagementService
from app.api.schemas import actions as ActionSchemas
from app.core.enums import TaskKey

# Упрощенная карта: Ключ -> (Класс Сервиса, Класс Pydantic-модели)
TASK_CONFIG_MAP = {
    TaskKey.LIKE_FEED: (FeedService, ActionSchemas.LikeFeedRequest),
    TaskKey.ADD_RECOMMENDED: (OutgoingRequestService, ActionSchemas.AddFriendsRequest),
    TaskKey.ACCEPT_FRIENDS: (IncomingRequestService, ActionSchemas.AcceptFriendsRequest),
    TaskKey.REMOVE_FRIENDS: (FriendManagementService, ActionSchemas.RemoveFriendsRequest),
    TaskKey.VIEW_STORIES: (StoryService, ActionSchemas.EmptyRequest),
    TaskKey.BIRTHDAY_CONGRATULATION: (AutomationService, ActionSchemas.BirthdayCongratulationRequest),
    TaskKey.MASS_MESSAGING: (MessageService, ActionSchemas.MassMessagingRequest),
    TaskKey.ETERNAL_ONLINE: (AutomationService, ActionSchemas.EmptyRequest),
    TaskKey.LEAVE_GROUPS: (GroupManagementService, ActionSchemas.LeaveGroupsRequest),
    TaskKey.JOIN_GROUPS: (GroupManagementService, ActionSchemas.JoinGroupsRequest),
}