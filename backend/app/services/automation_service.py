# --- backend/app/services/automation_service.py ---
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

class AutomationService(BaseVKService):
    """
    Сервис для выполнения автоматизаций, которые не вписываются
    в другие категории (например, поздравления, поддержание статуса).
    """

    async def get_birthday_congratulation_targets(self, params: BirthdayCongratulationRequest) -> List[Dict[str, Any]]:
        """
        Находит друзей-именинников и применяет к ним все фильтры.
        Используется для предпросмотра и для выполнения задачи.
        """
        friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="bdate,sex,online,last_seen,is_closed,status,city")
        if not friends:
            return []

        today = datetime.date.today()
        today_str = f"{today.day}.{today.month}"
        
        birthday_friends_raw = [f for f in friends if f.get("bdate") and f.get("bdate").startswith(today_str)]
        if not birthday_friends_raw:
            return []
            
        await self.emitter.send_log(f"Найдено именинников: {len(birthday_friends_raw)} чел. Применяем фильтры...", "info")
        
        birthday_friends_filtered = await apply_filters_to_profiles(birthday_friends_raw, params.filters)
        if not birthday_friends_filtered:
            return []
        
        if params.only_new_dialogs or params.only_unread:
            message_service = MessageService(self.db, self.user, self.emitter)
            await message_service._initialize_vk_api() 
            final_targets = await message_service.filter_targets_by_conversation_status(
                birthday_friends_filtered, params.only_new_dialogs, params.only_unread
            )
        else:
            final_targets = birthday_friends_filtered

        return final_targets

    async def congratulate_friends_with_birthday(self, params: BirthdayCongratulationRequest):
        """
        Выполняет логику поздравления друзей с Днем Рождения.
        """
        return await self._execute_logic(self._congratulate_friends_logic, params)

    async def _congratulate_friends_logic(self, params: BirthdayCongratulationRequest):
        """
        Приватный метод с основной логикой поздравления.
        """
        await self.emitter.send_log("Запуск задачи: Поздравление друзей с Днем Рождения.", "info")
        
        final_targets = await self.get_birthday_congratulation_targets(params)
        if not final_targets:
            await self.emitter.send_log("После всех фильтров не осталось именинников для поздравления.", "success")
            return
            
        await self.emitter.send_log(f"К поздравлению готово: {len(final_targets)} чел. Проверяем, кого уже поздравили...", "info")
        current_year = datetime.date.today().year
        stmt = select(SentCongratulation.friend_vk_id).where(
            and_(SentCongratulation.user_id == self.user.id, SentCongratulation.year == current_year)
        )
        already_congratulated_ids = {row[0] for row in (await self.db.execute(stmt)).all()}
        targets_to_process = [friend for friend in final_targets if friend['id'] not in already_congratulated_ids]

        if not targets_to_process:
            await self.emitter.send_log("Все найденные именинники на сегодня уже были поздравлены.", "success")
            return

        await self.emitter.send_log(f"Начинаем отправку поздравлений для {len(targets_to_process)} чел.", "info")
        processed_count = 0

        for friend in targets_to_process:
            friend_id = friend['id']
            sex = friend.get("sex")
            template = params.message_template_default
            if sex == 2 and params.message_template_male:
                template = params.message_template_male
            elif sex == 1 and params.message_template_female:
                template = params.message_template_female
            
            if params.humanized_sending.enabled:
                humanizer = MessageHumanizer(self.vk_api, self.emitter)
                result = await humanizer.send_messages_sequentially(
                    targets=[friend], template=template,
                    speed=params.humanized_sending.speed,
                    simulate_typing=params.humanized_sending.simulate_typing
                )
                if result > 0:
                    processed_count += 1
                    insert_stmt = insert(SentCongratulation).values(user_id=self.user.id, friend_vk_id=friend_id, year=current_year).on_conflict_do_nothing()
                    await self.db.execute(insert_stmt)
            else:
                message = template.replace("{name}", friend.get("first_name", ""))
                url = f"https://vk.com/id{friend_id}"
                await self.humanizer.imitate_simple_action()
                if await self.vk_api.send_message(friend_id, message):
                    insert_stmt = insert(SentCongratulation).values(user_id=self.user.id, friend_vk_id=friend_id, year=current_year).on_conflict_do_nothing()
                    await self.db.execute(insert_stmt)
                    await self.emitter.send_log(f"Успешно отправлено поздравление для {friend.get('first_name', '')}", "success", target_url=url)
                    processed_count += 1

        await self.emitter.send_log(f"Задача завершена. Отправлено поздравлений: {processed_count}.", "success")
        
    async def set_online_status(self, params: EternalOnlineRequest):
        """
        Устанавливает статус "онлайн" для пользователя.
        Вся сложная логика расписания вынесена в cron-обработчик.
        """
        return await self._execute_logic(self._set_online_status_logic)

    async def _set_online_status_logic(self):
        """
        Непосредственно вызывает метод VK API для установки статуса.
        """
        await self.emitter.send_log("Поддержание статуса 'онлайн'...", "debug")
        await self.vk_api.set_online()