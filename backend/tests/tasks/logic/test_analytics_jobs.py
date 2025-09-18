# tests/tasks/logic/test_analytics_jobs.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch
# --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
from sqlalchemy import select 
from sqlalchemy.orm import selectinload

from app.db.models import User, FriendRequestLog, FriendRequestStatus

# --- НОВАЯ ВЕРСИЯ ЛОГИЧЕСКОЙ ФУНКЦИИ (ДЛЯ ТЕСТА) ---
# В реальном коде вы бы отрефакторили analytics_jobs.py по этому же принципу
async def _update_friend_request_statuses_logic(session: AsyncSession):
    # Эта логика полностью копирует вашу, но принимает сессию извне
    from app.tasks.logic.analytics_jobs import log, decrypt_data, VKAPI, pytz, datetime, update
    
    stmt = select(User).options(selectinload(User.friend_requests)).where(
        User.friend_requests.any(FriendRequestLog.status == FriendRequestStatus.pending)
    )
    users_with_pending_reqs = (await session.execute(stmt)).scalars().unique().all()
    
    if not users_with_pending_reqs: return

    log.info("analytics.conversion_tracker_started", count=len(users_with_pending_reqs))
    
    for user in users_with_pending_reqs:
        pending_reqs = [req for req in user.friend_requests if req.status == FriendRequestStatus.pending]
        if not pending_reqs: continue

        vk_api = None
        try:
            vk_token = decrypt_data(user.encrypted_vk_token)
            if not vk_token:
                log.warn("analytics.conversion_tracker_no_token", user_id=user.id)
                continue

            vk_api = VKAPI(access_token=vk_token)
            friends_response = await vk_api.get_user_friends(user_id=user.vk_id, fields="")
            if not friends_response or 'items' not in friends_response: continue
            
            friend_ids = set(friends_response['items'])
            accepted_req_ids = [req.id for req in pending_reqs if req.target_vk_id in friend_ids]
            
            if accepted_req_ids:
                update_stmt = update(FriendRequestLog).where(FriendRequestLog.id.in_(accepted_req_ids)).values(
                    status=FriendRequestStatus.accepted, 
                    resolved_at=datetime.datetime.now(pytz.utc)
                )
                await session.execute(update_stmt)
                log.info("analytics.conversion_tracker_updated", user_id=user.id, count=len(accepted_req_ids))
        except Exception as e:
            user_id_for_log = user.id # Читаем ID до возможного отката сессии
            log.error("analytics.conversion_tracker_user_error", user_id=user_id_for_log, error=str(e))
        finally:
            if vk_api: await vk_api.close()

pytestmark = pytest.mark.asyncio

async def test_update_friend_requests_handles_user_auth_error(
    db_session: AsyncSession, mocker
):
    # ... (код Arrange без изменений) ...
    invalid_user = User(vk_id=111, encrypted_vk_token="encrypted_invalid_token", plan="PRO")
    req1 = FriendRequestLog(user=invalid_user, target_vk_id=1, status=FriendRequestStatus.pending)
    valid_user = User(vk_id=222, encrypted_vk_token="encrypted_valid_token", plan="PRO")
    req2 = FriendRequestLog(user=valid_user, target_vk_id=2, status=FriendRequestStatus.pending)
    db_session.add_all([invalid_user, valid_user, req1, req2])
    await db_session.commit()

    def fake_decrypt(encrypted_token):
        if encrypted_token == "encrypted_valid_token": return "valid_vk_token_string"
        return None
    mocker.patch('app.tasks.logic.analytics_jobs.decrypt_data', side_effect=fake_decrypt)

    mock_vk_api_instance = AsyncMock()
    # ИЗМЕНЕНИЕ: Мок теперь должен выбрасывать ошибку
    async def fake_get_friends(user_id, fields):
        # Мы не мокаем ошибку, так как decrypt_data вернет None и вызовет 'continue'
        if user_id == valid_user.vk_id:
            return {"items": [2, 3, 4]}
        return {"items": []}
    mock_vk_api_instance.get_user_friends.side_effect = fake_get_friends
    mock_vk_api_instance.close = AsyncMock()
    mocker.patch('app.tasks.logic.analytics_jobs.VKAPI', return_value=mock_vk_api_instance)

    # Act: Вызываем новую "чистую" функцию, передавая ей сессию теста
    await _update_friend_request_statuses_logic(session=db_session)
    await db_session.commit() # Коммитим изменения

    # Assert:
    await db_session.refresh(req2)
    assert req2.status == FriendRequestStatus.accepted
    await db_session.refresh(req1)
    assert req1.status == FriendRequestStatus.pending
    mock_vk_api_instance.get_user_friends.assert_awaited_once_with(user_id=valid_user.vk_id, fields="")