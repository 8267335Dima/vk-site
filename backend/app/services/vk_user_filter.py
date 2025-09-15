# --- backend/app/services/vk_user_filter.py ---

import datetime
from typing import Dict, Any, List

# Убираем Optional[VKAPI], так как он больше не нужен
from app.api.schemas.actions import ActionFilters


async def apply_filters_to_profiles(
    profiles: List[Dict[str, Any]],
    filters: ActionFilters,
) -> List[Dict[str, Any]]:
    """
    Применяет фильтры к списку профилей VK на основе уже имеющихся данных.
    Эта функция является "чистой" и не делает внешних запросов.
    """
    filtered_profiles = []
    now_ts = datetime.datetime.now(datetime.UTC).timestamp()

    for profile in profiles:
        # --- УЛУЧШЕНИЕ: Более явная и централизованная обработка "собачек" ---
        deactivated_status = profile.get('deactivated')
        
        # Если задача НЕ на удаление, пропускаем любых деактивированных пользователей
        if not filters.remove_banned and deactivated_status:
            continue
        
        # Если задача на удаление, но флаг `remove_banned` снят, то тоже пропускаем
        if filters.remove_banned is False and deactivated_status:
            continue
        # В остальных случаях (когда задача на удаление и флаг `remove_banned` активен),
        # "собачки" будут проходить дальше и обрабатываться логикой задачи.

        # Фильтр по закрытому профилю
        # `is_closed` может отсутствовать, по умолчанию считаем профиль закрытым
        if not filters.allow_closed_profiles and profile.get('is_closed', True):
            continue
        
        # Фильтр по полу (0 - любой пол)
        if filters.sex and profile.get('sex') != filters.sex: 
            continue
            
        # Фильтр по статусу "онлайн"
        if filters.is_online and not profile.get('online', 0): 
            continue
        
        # Фильтр по последнему визиту
        last_seen_ts = profile.get('last_seen', {}).get('time', 0)
        if last_seen_ts > 0: # Проверяем только если дата визита известна
            hours_since_seen = (now_ts - last_seen_ts) / 3600
            if filters.last_seen_hours and hours_since_seen > filters.last_seen_hours:
                continue
            if filters.last_seen_days and hours_since_seen > (filters.last_seen_days * 24):
                continue
        elif filters.last_seen_hours or filters.last_seen_days: 
            # Если фильтр по дате есть, а даты нет, то пропускаем профиль
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
            
        filtered_profiles.append(profile)

    return filtered_profiles