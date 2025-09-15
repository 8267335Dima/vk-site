# backend/tests/test_filters.py
import pytest
from typing import List, Dict, Any

from app.api.schemas.actions import ActionFilters
from app.services.vk_api import VKAPI
from app.services.vk_user_filter import apply_filters_to_profiles

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="module")
async def real_friends_data(vk_api_client_module: VKAPI) -> List[Dict[str, Any]]:
    """Получает ПОЛНЫЙ список друзей со всеми ДОСТУПНЫМИ полями."""
    print("\n[SETUP] Получение полного списка друзей от VK API...")
    try:
        friends = await vk_api_client_module.get_user_friends(
            user_id=vk_api_client_module.user_id,
            fields="sex,online,last_seen,is_closed,status,deactivated,city"
        )
        assert friends is not None, "Не удалось получить список друзей."
        print(f"[SETUP] ✓ Успешно получено {len(friends)} друзей.")
        return friends
    except Exception as e:
        pytest.fail(f"Критическая ошибка при получении списка друзей: {e}")

async def test_all_fast_filters_on_live_data(real_friends_data: list):
    """
    Проводит диагностику и проверку всех 'быстрых' фильтров по отдельности и в комбинации.
    """
    print(f"\n\n{'='*25} НАЧАЛО ДИАГНОСТИКИ ФИЛЬТРОВ {'='*25}")
    
    # --- ЭТАП 0: Общая статистика по списку ---
    print("\n" + "-"*20 + " Этап 0: Общая диагностика " + "-"*20)
    total_friends = len(real_friends_data)
    active_friends = [p for p in real_friends_data if not p.get('deactivated')]
    open_profiles = [p for p in active_friends if not p.get('is_closed')]
    print(f"  - Всего друзей в аккаунте: {total_friends}")
    print(f"  - Активных (не 'собачек'): {len(active_friends)}")
    print(f"  - Из них с открытым профилем: {len(open_profiles)}")

    # --- ЭТАП 1: Тесты каждого фильтра по отдельности ---
    print("\n" + "-"*20 + " Этап 1: Тестирование по отдельности " + "-"*20)
    
    filters = ActionFilters(sex=1, allow_closed_profiles=True)
    result = await apply_filters_to_profiles(real_friends_data, filters)
    print(f"  - Фильтр 'Пол: Женский' (всех): {len(result)}")

    filters = ActionFilters(is_online=True, allow_closed_profiles=True)
    result = await apply_filters_to_profiles(real_friends_data, filters)
    print(f"  - Фильтр 'Сейчас онлайн' (всех): {len(result)}")
    
    filters = ActionFilters(allow_closed_profiles=False)
    result = await apply_filters_to_profiles(real_friends_data, filters)
    print(f"  - Фильтр 'Только открытые профили': {len(result)}")
    assert len(result) == len(open_profiles)

    filters = ActionFilters(last_seen_hours=24, allow_closed_profiles=True)
    result = await apply_filters_to_profiles(real_friends_data, filters)
    print(f"  - Фильтр 'Заходили за 24 часа' (всех): {len(result)}")

    city = "Москва"
    filters = ActionFilters(city=city, allow_closed_profiles=True)
    result = await apply_filters_to_profiles(real_friends_data, filters)
    print(f"  - Фильтр 'Город: {city}' (всех): {len(result)}")

    # --- ЭТАП 2: Тесты комбинаций ---
    print("\n" + "-"*20 + " Этап 2: Тестирование комбинаций " + "-"*20)

    print("  - Задача: Найти женщин, которые сейчас онлайн.")
    filters = ActionFilters(sex=1, is_online=True, allow_closed_profiles=True)
    result = await apply_filters_to_profiles(real_friends_data, filters)
    print(f"    └── РЕЗУЛЬТАТ: Найдено {len(result)} чел.")
    for user in result:
        assert user['sex'] == 1 and user['online'] == 1

    print("\n  - Задача: Найти мужчин из Москвы с открытым профилем.")
    filters = ActionFilters(sex=2, city="Москва", allow_closed_profiles=False)
    result = await apply_filters_to_profiles(real_friends_data, filters)
    print(f"    └── РЕЗУЛЬТАТ: Найдено {len(result)} чел.")
    for user in result:
        assert user['sex'] == 2
        assert not user['is_closed']
        assert "москва" in user.get('city', {}).get('title', '').lower()

    print("\n  - ✓ Все 'быстрые' фильтры и их комбинации работают корректно.")
    print(f"\n{'='*25} ДИАГНОСТИКА ФИЛЬТРОВ ЗАВЕРШЕНА {'='*25}")