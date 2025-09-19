# backend/app/tasks/task_maps.py
from typing import Union

from app.services.feed_service import FeedService
from app.services.incoming_request_service import IncomingRequestService
from app.services.outgoing_request_service import OutgoingRequestService
from app.services.friend_management_service import FriendManagementService
from app.services.story_service import StoryService
from app.services.automation_service import AutomationService
from app.services.message_service import MessageService
from app.services.group_management_service import GroupManagementService

from app.api.schemas.actions import (
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest, JoinGroupsRequest, LeaveGroupsRequest,
    BirthdayCongratulationRequest, EternalOnlineRequest
)

from app.core.enums import TaskKey

AnyTaskRequest = Union[
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest, JoinGroupsRequest, LeaveGroupsRequest,
    BirthdayCongratulationRequest, EternalOnlineRequest
]

TASK_FUNC_MAP = {
    TaskKey.ACCEPT_FRIENDS: "accept_friend_requests_task",
    TaskKey.LIKE_FEED: "like_feed_task",
    TaskKey.ADD_RECOMMENDED: "add_recommended_friends_task",
    TaskKey.VIEW_STORIES: "view_stories_task",
    TaskKey.REMOVE_FRIENDS: "remove_friends_by_criteria_task",
    TaskKey.MASS_MESSAGING: "mass_messaging_task",
    TaskKey.JOIN_GROUPS: "join_groups_by_criteria_task",
    TaskKey.LEAVE_GROUPS: "leave_groups_by_criteria_task",
    TaskKey.BIRTHDAY_CONGRATULATION: "birthday_congratulation_task",
    TaskKey.ETERNAL_ONLINE: "eternal_online_task",
}

PREVIEW_SERVICE_MAP = {
    TaskKey.ADD_RECOMMENDED: (OutgoingRequestService, "get_add_recommended_targets", AddFriendsRequest),
    TaskKey.ACCEPT_FRIENDS: (IncomingRequestService, "get_accept_friends_targets", AcceptFriendsRequest),
    TaskKey.REMOVE_FRIENDS: (FriendManagementService, "get_remove_friends_targets", RemoveFriendsRequest),
    TaskKey.MASS_MESSAGING: (MessageService, "get_mass_messaging_targets", MassMessagingRequest),
    TaskKey.LEAVE_GROUPS: (GroupManagementService, "get_leave_groups_targets", LeaveGroupsRequest),
    TaskKey.JOIN_GROUPS: (GroupManagementService, "get_join_groups_targets", JoinGroupsRequest),
    TaskKey.BIRTHDAY_CONGRATULATION: (AutomationService, "get_birthday_congratulation_targets", BirthdayCongratulationRequest),
}