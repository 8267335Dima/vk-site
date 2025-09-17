# backend/app/services/vk_user_filter.py

import datetime
from typing import Dict, Any, List

from app.api.schemas.actions import ActionFilters


async def apply_filters_to_profiles(
    profiles: List[Dict[str, Any]],
    filters: ActionFilters,
) -> List[Dict[str, Any]]:
    """
    Применяет различные фильтры к списку профилей VK.

    Эта функция является "чистой" и не делает внешних запросов к API.
    Она работает с уже полученными данными профилей.

    Args:
        profiles: Список словарей, где каждый словарь - это профиль пользователя VK.
        filters: Pydantic-модель с параметрами для фильтрации.

    Returns:
        Отфильтрованный список профилей.
    """
    filtered_profiles = []
    # Получаем текущее время один раз для эффективности
    now_ts = datetime.datetime.now(datetime.UTC).timestamp()

    for profile in profiles:
        # --- Обработка деактивированных ("забаненных", "удаленных") профилей ---
        deactivated_status = profile.get('deactivated')
        if deactivated_status:
            # Если у профиля есть статус (banned/deleted) и фильтр `remove_banned`
            # НЕ установлен в True, то мы пропускаем такой профиль.
            # Это позволяет включать "собачек" в выборку только для задач
            # по чистке, где этот флаг намеренно выставляется.
            if not filters.remove_banned:
                continue

        # --- Стандартные фильтры, исключающие профиль из выборки ---

        # Фильтр по полу (0 - любой пол, поэтому проверяем только если 1 или 2)
        if filters.sex and profile.get('sex') != filters.sex:
            continue

        # Фильтр по статусу "онлайн"
        if filters.is_online and not profile.get('online', 0):
            continue

        # Фильтр по последнему визиту
        last_seen_ts = profile.get('last_seen', {}).get('time', 0)
        if last_seen_ts > 0:  # Проверяем только если дата визита известна
            hours_since_seen = (now_ts - last_seen_ts) / 3600

            # **ЛОГИКА ДЛЯ УДАЛЕНИЯ НЕАКТИВНЫХ**
            # Если фильтр `last_seen_days` активен, мы хотим удалить тех,
            # кто НЕ заходил N дней. Значит, мы должны ПРОПУСТИТЬ тех,
            # кто заходил НЕДАВНО (меньше или равно N дней назад).
            if filters.last_seen_days and hours_since_seen <= (filters.last_seen_days * 24):
                continue

            # **ЛОГИКА ДЛЯ ДОБАВЛЕНИЯ АКТИВНЫХ**
            # Если фильтр `last_seen_hours` активен, мы хотим добавить тех,
            # кто заходил в течение N часов. Значит, мы должны ПРОПУСТИТЬ тех,
            # кто НЕ заходил БОЛЬШЕ N часов.
            if filters.last_seen_hours and hours_since_seen > filters.last_seen_hours:
                continue

        elif filters.last_seen_days or filters.last_seen_hours:
            # Если фильтр по дате есть, а у профиля даты нет, то пропускаем его
            continue

        # Фильтр по ключевому слову в статусе
        status_keyword = (filters.status_keyword or "").lower().strip()
        if status_keyword and status_keyword not in profile.get('status', '').lower():
            continue

        # Фильтр по городу
        city_filter = (filters.city or "").lower().strip()
        if city_filter and city_filter not in profile.get('city', {}).get('title', '').lower():
            continue

        # Фильтр для лайков в ленте: только посты с фото
        if filters.only_with_photo and not profile.get('photo_id'):
            continue

        # Если профиль прошел все проверки, добавляем его в итоговый список
        filtered_profiles.append(profile)

    return filtered_profiles