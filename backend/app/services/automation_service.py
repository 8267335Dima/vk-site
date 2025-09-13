# backend/app/services/automation_service.py
import datetime
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.services.vk_api import VKAccessDeniedError
from app.db.models import SentCongratulation
from app.api.schemas.actions import BirthdayCongratulationRequest

class AutomationService(BaseVKService):

    async def congratulate_friends_with_birthday(self, params: BirthdayCongratulationRequest):
        return await self._execute_logic(self._congratulate_friends_logic, params)

    async def _congratulate_friends_logic(self, params: BirthdayCongratulationRequest):
        await self.emitter.send_log("Запуск задачи: Поздравление друзей с Днем Рождения.", "info")
        
        friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="bdate,sex")
        if not friends:
            await self.emitter.send_log("Не удалось получить список друзей.", "warning")
            return

        today = datetime.date.today()
        today_str = f"{today.day}.{today.month}"
        
        birthday_friends = [f for f in friends if f.get("bdate") and f.get("bdate").startswith(today_str)]

        if not birthday_friends:
            await self.emitter.send_log("Сегодня нет дней рождения у друзей.", "info")
            return

        await self.emitter.send_log(f"Найдено именинников: {len(birthday_friends)} чел. Начинаем поздравлять.", "info")

        current_year = today.year
        stmt = select(SentCongratulation.friend_vk_id).where(
            and_(SentCongratulation.user_id == self.user.id, SentCongratulation.year == current_year)
        )
        already_congratulated_ids = {row[0] for row in (await self.db.execute(stmt)).all()}

        processed_count = 0
        for friend in birthday_friends:
            friend_id = friend['id']
            if friend_id in already_congratulated_ids:
                continue

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