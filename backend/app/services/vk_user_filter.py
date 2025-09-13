# backend/app/services/vk_user_filter.py
import datetime
from typing import Dict, Any, List

def apply_filters_to_profiles(profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Централизованная функция для фильтрации профилей VK по заданным критериям.
    """
    if not filters:
        return profiles

    filtered_profiles = []
    now_ts = datetime.datetime.now().timestamp()

    for profile in profiles:
        # Пропуск деактивированных (banned/deleted) профилей, если это не чистка друзей
        if filters.get('remove_banned') is None and profile.get('deactivated'):
            continue
            
        # Фильтр по закрытому профилю
        if not filters.get('allow_closed_profiles', False) and profile.get('is_closed', True):
            continue

        # Фильтр по полу (0 - любой)
        if filters.get('sex') and profile.get('sex') != filters['sex']:
            continue
            
        # Фильтр по статусу "онлайн"
        if filters.get('is_online', False) and not profile.get('online', 0):
            continue

        # Фильтр по ключевому слову в статусе
        status_keyword = filters.get('status_keyword', '').lower()
        if status_keyword and status_keyword not in profile.get('status', '').lower():
            continue

        # Фильтры по времени последнего посещения
        last_seen_ts = profile.get('last_seen', {}).get('time', 0)
        if last_seen_ts:
            last_seen_hours = filters.get('last_seen_hours')
            if last_seen_hours and (now_ts - last_seen_ts) > (last_seen_hours * 3600):
                continue

            last_seen_days = filters.get('last_seen_days')
            if last_seen_days and (now_ts - last_seen_ts) > (last_seen_days * 86400):
                continue
        
        # Фильтры по количеству друзей/подписчиков
        counters = profile.get('counters', {})
        friends_count = counters.get('friends', 0)
        followers_count = counters.get('followers', 0)

        min_friends = filters.get('min_friends')
        if min_friends is not None and friends_count < min_friends:
            continue
        
        max_friends = filters.get('max_friends')
        if max_friends is not None and friends_count > max_friends:
            continue
            
        min_followers = filters.get('min_followers')
        if min_followers is not None and followers_count < min_followers:
            continue

        max_followers = filters.get('max_followers')
        if max_followers is not None and followers_count > max_followers:
            continue

        filtered_profiles.append(profile)
        
    return filtered_profiles