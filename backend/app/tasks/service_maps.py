# backend/app/tasks/service_maps.py
# Этот файл разрывает циклическую зависимость между runner.py и scenario_service.py
# Он является центральным местом для сопоставления задач с их исполнителями (сервисами).

# Импортируем все необходимые сервисы и схемы
from app.services.feed_service import FeedService
from app.services.incoming_request_service import IncomingRequestService
from app.services.outgoing_request_service import OutgoingRequestService
from app.services.friend_management_service import FriendManagementService
from app.services.story_service import StoryService
from app.services.automation_service import AutomationService
from app.services.message_service import MessageService
from app.services.group_management_service import GroupManagementService
from app.core.constants import TaskKey
from app.api.schemas import actions as ActionSchemas

# Карта для исполнителя сценариев (Service, method_name)
TASK_SERVICE_MAP = {
    TaskKey.LIKE_FEED: (FeedService, "like_newsfeed"),
    TaskKey.ADD_RECOMMENDED: (OutgoingRequestService, "add_recommended_friends"),
    TaskKey.ACCEPT_FRIENDS: (IncomingRequestService, "accept_friend_requests"),
    TaskKey.REMOVE_FRIENDS: (FriendManagementService, "remove_friends_by_criteria"),
    TaskKey.VIEW_STORIES: (StoryService, "view_stories"),
    TaskKey.BIRTHDAY_CONGRATULATION: (AutomationService, "congratulate_friends_with_birthday"),
    TaskKey.MASS_MESSAGING: (MessageService, "send_mass_message"),
    TaskKey.ETERNAL_ONLINE: (AutomationService, "set_online_status"),
    TaskKey.LEAVE_GROUPS: (GroupManagementService, "leave_groups_by_criteria"),
    TaskKey.JOIN_GROUPS: (GroupManagementService, "join_groups_by_criteria"),
}

# Полная карта для runner.py (Service, method_name, ParamsModel)
# Теперь она живет здесь, а не в runner.py
TASK_CONFIG_MAP = {
    TaskKey.LIKE_FEED: (FeedService, "like_newsfeed", ActionSchemas.LikeFeedRequest),
    TaskKey.ADD_RECOMMENDED: (OutgoingRequestService, "add_recommended_friends", ActionSchemas.AddFriendsRequest),
    TaskKey.ACCEPT_FRIENDS: (IncomingRequestService, "accept_friend_requests", ActionSchemas.AcceptFriendsRequest),
    TaskKey.REMOVE_FRIENDS: (FriendManagementService, "remove_friends_by_criteria", ActionSchemas.RemoveFriendsRequest),
    TaskKey.VIEW_STORIES: (StoryService, "view_stories", ActionSchemas.EmptyRequest),
    TaskKey.BIRTHDAY_CONGRATULATION: (AutomationService, "congratulate_friends_with_birthday", ActionSchemas.BirthdayCongratulationRequest),
    TaskKey.MASS_MESSAGING: (MessageService, "send_mass_message", ActionSchemas.MassMessagingRequest),
    TaskKey.ETERNAL_ONLINE: (AutomationService, "set_online_status", ActionSchemas.EmptyRequest),
    TaskKey.LEAVE_GROUPS: (GroupManagementService, "leave_groups_by_criteria", ActionSchemas.LeaveGroupsRequest),
    TaskKey.JOIN_GROUPS: (GroupManagementService, "join_groups_by_criteria", ActionSchemas.JoinGroupsRequest),
}