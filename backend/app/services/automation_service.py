# --- backend/app/services/automation_service.py ---
import datetime
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.services.vk_api import VKAccessDeniedError
from app.db.models import SentCongratulation
from app.api.schemas.actions import BirthdayCongratulationRequest
from app.services.vk_user_filter import apply_filters_to_profiles
from app.services.message_service import MessageService # <--- НОВЫЙ ИМПОРТ

class AutomationService(BaseVKService):

    async def congratulate_friends_with_birthday(self, params: BirthdayCongratulationRequest):
        return await self._execute_logic(self._congratulate_friends_logic, params)

    async def _congratulate_friends_logic(self, params: BirthdayCongratulationRequest):
        await self.emitter.send_log("Запуск задачи: Поздравление друзей с Днем Рождения.", "info")
        
        friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="bdate,sex,online,last_seen,is_closed,status,city")
        if not friends:
            await self.emitter.send_log("Не удалось получить список друзей.", "warning")
            return

        today = datetime.date.today()
        today_str = f"{today.day}.{today.month}"
        
        birthday_friends_raw = [f for f in friends if f.get("bdate") and f.get("bdate").startswith(today_str)]

        if not birthday_friends_raw:
            await self.emitter.send_log("Сегодня нет дней рождения у друзей.", "info")
            return
            
        await self.emitter.send_log(f"Найдено именинников: {len(birthday_friends_raw)} чел. Применяем стандартные фильтры...", "info")
        
        # Шаг 1: Применяем стандартные фильтры (пол, онлайн и т.д.)
        birthday_friends_filtered = await apply_filters_to_profiles(birthday_friends_raw, params.filters)
        
        if not birthday_friends_filtered:
            await self.emitter.send_log("После стандартных фильтров не осталось именинников.", "success")
            return
        
        # Шаг 2: Применяем фильтры по диалогам, если они включены
        if params.only_new_dialogs or params.only_unread:
            message_service = MessageService(self.db, self.user, self.emitter)
            # Инициализируем vk_api внутри message_service
            await message_service._initialize_vk_api() 
            final_targets = await message_service.filter_targets_by_conversation_status(
                birthday_friends_filtered, params.only_new_dialogs, params.only_unread
            )
        else:
            final_targets = birthday_friends_filtered

        if not final_targets:
            await self.emitter.send_log("После фильтрации диалогов не осталось именинников для поздравления.", "success")
            return
            
        await self.emitter.send_log(f"После всех фильтров осталось: {len(final_targets)} чел. Начинаем поздравлять.", "info")

        current_year = today.year
        stmt = select(SentCongratulation.friend_vk_id).where(
            and_(SentCongratulation.user_id == self.user.id, SentCongratulation.year == current_year)
        )
        already_congratulated_ids = {row[0] for row in (await self.db.execute(stmt)).all()}

        processed_count = 0
        for friend in final_targets: # <--- Используем окончательный список
            friend_id = friend['id']
            if friend_id in already_congratulated_ids:
                continue

            # ... (остальная логика отправки поздравлений без изменений) ...
            name = friend.get("first_name", "")
            sex = friend.get("sex")

            template = params.message_template_default
            if sex == 2 and params.message_template_male:
                template = params.message_template_male
            elif sex == 1 and params.message_template_female:
                template = params.message_template_female

            message = template.replace("{name}", name)
            url = f"https://vk.com/id{friend_id}"

            await self.humanizer.imitate_simple_action()

            try:
                if await self.vk_api.send_message(friend_id, message):
                    insert_stmt = insert(SentCongratulation).values(
                        user_id=self.user.id, friend_vk_id=friend_id, year=current_year
                    ).on_conflict_do_nothing()
                    await self.db.execute(insert_stmt)
                    
                    await self.emitter.send_log(f"Успешно отправлено поздравление для {name}", "success", target_url=url)
                    processed_count += 1
                else:
                    await self.emitter.send_log(f"Не удалось отправить поздравление для {name}.", "error", target_url=url)
            except VKAccessDeniedError:
                await self.emitter.send_log(f"Не удалось отправить сообщение для {name} (профиль закрыт или ЧС).", "warning", target_url=url)
        
        await self.emitter.send_log(f"Задача завершена. Отправлено поздравлений: {processed_count}.", "success")
        
    async def set_online_status(self):
        return await self._execute_logic(self._set_online_status_logic)

    async def _set_online_status_logic(self):
        await self.emitter.send_log("Поддержание статуса 'онлайн'...", "debug")
        await self.vk_api.set_online()
        await self.emitter.send_log("Статус 'онлайн' успешно обновлен.", "success")