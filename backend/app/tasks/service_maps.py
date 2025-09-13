# backend/app/tasks/service_maps.py
# Этот файл разрывает циклическую зависимость между runner.py и scenario_service.py

from app.services.feed_service import FeedService
from app.services.incoming_request_service import IncomingRequestService
from app.services.outgoing_request_service import OutgoingRequestService
from app.services.friend_management_service import FriendManagementService
from app.services.story_service import StoryService
from app.services.automation_service import AutomationService
from app.services.message_service import MessageService
from app.services.group_management_service import GroupManagementService
from app.core.constants import TaskKey

# Эта карта специально предназначена для исполнителя сценариев, которому не нужна Pydantic-модель.
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