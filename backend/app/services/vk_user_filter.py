# backend/app/services/vk_user_filter.py
import datetime
from typing import Dict, Any, List, Optional
from app.api.schemas.actions import ActionFilters
from app.services.vk_api import VKAPI

async def apply_filters_to_profiles(
    profiles: List[Dict[str, Any]],
    filters: ActionFilters,
    vk_api: Optional[VKAPI] = None  # Параметр vk_api оставлен для совместимости, но не используется
) -> List[Dict[str, Any]]:
    """
    Применяет "быстрые" фильтры (пол, город и т.д.) на основе уже имеющихся данных.
    Фильтрация по счетчикам (друзья/подписчики) здесь не производится.
    """
    filtered_profiles = []
    now_ts = datetime.datetime.now().timestamp()

    for profile in profiles:
        # Пропускаем "собачек", если это не задача на удаление
        if not filters.remove_banned and profile.get('deactivated'):
            continue
        
        # Фильтр по закрытому профилю
        if not filters.allow_closed_profiles and profile.get('is_closed', True):
            continue
        
        # Простые фильтры
        if filters.sex and profile.get('sex') != filters.sex: continue
        if filters.is_online and not profile.get('online', 0): continue
        
        last_seen_ts = profile.get('last_seen', {}).get('time', 0)
        if filters.last_seen_hours and (not last_seen_ts or (now_ts - last_seen_ts) > (filters.last_seen_hours * 3600)): continue
        if filters.last_seen_days and (not last_seen_ts or (now_ts - last_seen_ts) > (filters.last_seen_days * 86400)): continue
        
        status_keyword = (filters.status_keyword or "").lower().strip()
        if status_keyword and status_keyword not in profile.get('status', '').lower(): continue
        
        city_filter = (filters.city or "").lower().strip()
        if city_filter and city_filter not in profile.get('city', {}).get('title', '').lower(): continue
        
        filtered_profiles.append(profile)

    return filtered_profiles