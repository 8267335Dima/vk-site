import datetime
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import SentCongratulation
from app.api.schemas.actions import BirthdayCongratulationRequest, EternalOnlineRequest
from app.services.vk_user_filter import apply_filters_to_profiles
from app.services.message_service import MessageService
from app.services.message_humanizer import MessageHumanizer
from typing import List, Dict, Any
from .interfaces import IExecutableTask, IPreviewableTask

class AutomationService(BaseVKService, IExecutableTask, IPreviewableTask):
    async def get_targets(self, params: BirthdayCongratulationRequest) -> List[Dict[str, Any]]:
        await self._initialize_vk_api()
        friends_response = await self.vk_api.get_user_friends(self.user.vk_id, fields="bdate,sex,online,last_seen,is_closed,status,city")
        if not friends_response or not friends_response.get('items'):
            return []
        friends = friends_response.get('items', [])
        today_str = f"{datetime.date.today().day}.{datetime.date.today().month}"
        birthday_friends_raw = [f for f in friends if f.get("bdate") and f.get("bdate").startswith(today_str)]
        if not birthday_friends_raw:
            return []
        birthday_friends_filtered = await apply_filters_to_profiles(birthday_friends_raw, params.filters)
        if not birthday_friends_filtered:
            return []
        if params.only_new_dialogs or params.only_unread:
            message_service = MessageService(self.db, self.user, self.emitter)
            message_service.vk_api = self.vk_api
            return await message_service.filter_targets_by_conversation_status(
                birthday_friends_filtered, params.only_new_dialogs, params.only_unread
            )
        return birthday_friends_filtered

    async def execute(self, params: BirthdayCongratulationRequest | EternalOnlineRequest) -> str:
        await self._initialize_vk_api()
        if isinstance(params, BirthdayCongratulationRequest):
            return await self._congratulate_friends_logic(params)
        elif isinstance(params, EternalOnlineRequest):
            return await self._set_online_status_logic()
        return "Неизвестный тип задачи для AutomationService."

    async def _congratulate_friends_logic(self, params: BirthdayCongratulationRequest) -> str:
        stats = await self._get_today_stats()
        final_targets = await self.get_targets(params)
        if not final_targets:
            return "Не осталось именинников для поздравления после применения фильтров."
        current_year = datetime.date.today().year
        stmt = select(SentCongratulation.friend_vk_id).where(
            and_(SentCongratulation.user_id == self.user.id, SentCongratulation.year == current_year)
        )
        already_congratulated_ids = {row[0] for row in (await self.db.execute(stmt)).all()}
        targets_to_process = [friend for friend in final_targets if friend['id'] not in already_congratulated_ids]
        if not targets_to_process:
            return "Все найденные именинники на сегодня уже были поздравлены."
        processed_count = 0
        for friend in targets_to_process:
            if stats.messages_sent_count >= self.user.daily_message_limit:
                break
            sex = friend.get("sex")
            template = params.message_template_male if sex == 2 and params.message_template_male else \
                       params.message_template_female if sex == 1 and params.message_template_female else \
                       params.message_template_default
            is_sent_successfully = False
            humanizer = MessageHumanizer(self.vk_api, self.emitter)
            sent_count = await humanizer.send_messages_sequentially(
                targets=[friend], template=template, speed=params.humanized_sending.speed,
                simulate_typing=params.humanized_sending.simulate_typing
            )
            if sent_count > 0:
                is_sent_successfully = True
            if is_sent_successfully:
                processed_count += 1
                await self._increment_stat(stats, 'messages_sent_count')
                insert_stmt = insert(SentCongratulation).values(user_id=self.user.id, friend_vk_id=friend['id'], year=current_year).on_conflict_do_nothing()
                await self.db.execute(insert_stmt)
        return f"Задача завершена. Отправлено поздравлений: {processed_count}."

    async def _set_online_status_logic(self) -> str:
        await self.vk_api.account.setOnline()
        return "Статус 'онлайн' успешно установлен."