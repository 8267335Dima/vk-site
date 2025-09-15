# backend/tests/test_filter_diagnostics.py

import pytest
from typing import List, Dict, Any
from app.api.schemas.actions import ActionFilters
from app.services.vk_api import VKAPI
from app.services.vk_user_filter import apply_filters_to_profiles

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="module")
async def real_friends_data(vk_api_client: VKAPI) -> List[Dict[str, Any]]:
    """Получает полный список друзей со всеми доступными полями один раз."""
    print("\n[DIAGNOSTICS_SETUP] Получение полного списка друзей от VK API...")
    try:
        friends = await vk_api_client.get_user_friends(
            user_id=vk_api_client.user_id,
            fields="sex,online,last_seen,is_closed,status,deactivated,city"
        )
        assert friends is not None, "Не удалось получить список друзей."
        print(f"[DIAGNOSTICS_SETUP] ✓ Успешно получено {len(friends)} друзей.")
        return friends
    except Exception as e:
        pytest.fail(f"Критическая ошибка при получении списка друзей: {e}")

async def test_all_fast_filters_on_live_data(real_friends_data: list):
    """
    Проводит диагностику и проверку всех 'быстрых' фильтров по отдельности и в комбинации.
    Этот тест ничего не меняет, только выводит информацию.
    """
    print(f"\n\n{'='*25} НАЧАЛО ДИАГНОСТИКИ ФИЛЬТРОВ {'='*25}")
    
    # --- Этап 0: Общая статистика ---
    print("\n" + "-"*20 + " Этап 0: Общая диагностика " + "-"*20)
    total_friends = len(real_friends_data)
    active_friends = [p for p in real_friends_data if not p.get('deactivated')]
    open_profiles = [p for p in active_friends if not p.get('is_closed')]
    print(f"  - Всего друзей в аккаунте: {total_friends}")
    print(f"  - Активных (не 'собачек'): {len(active_friends)}")
    print(f"  - Из них с открытым профилем: {len(open_profiles)}")

    # --- Этап 1: Тесты каждого фильтра по отдельности ---
    print("\n" + "-"*20 + " Этап 1: Тестирование по отдельности " + "-"*20)
    
    filters_female = ActionFilters(sex=1, allow_closed_profiles=True)
    result_female = await apply_filters_to_profiles(real_friends_data, filters_female)
    print(f"  - Фильтр 'Пол: Женский': Найдено {len(result_female)} чел.")

    filters_online = ActionFilters(is_online=True, allow_closed_profiles=True)
    result_online = await apply_filters_to_profiles(real_friends_data, filters_online)
    print(f"  - Фильтр 'Сейчас онлайн': Найдено {len(result_online)} чел.")

    # --- Этап 2: Тесты комбинаций ---
    print("\n" + "-"*20 + " Этап 2: Тестирование комбинаций " + "-"*20)
    print("  - Комбинация: Женщины, которые сейчас онлайн.")
    filters_combo = ActionFilters(sex=1, is_online=True, allow_closed_profiles=True)
    result_combo = await apply_filters_to_profiles(real_friends_data, filters_combo)
    print(f"    └── РЕЗУЛЬТАТ: Найдено {len(result_combo)} чел.")
    
    print(f"\n{'='*25} ДИАГНОСТИКА ФИЛЬТРОВ ЗАВЕРШЕНА {'='*25}")