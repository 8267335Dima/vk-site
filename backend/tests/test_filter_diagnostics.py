# --- backend/tests/test_filter_diagnostics.py ---
import pytest
from typing import List, Dict, Any
from app.api.schemas.actions import ActionFilters
from app.services.vk_api import VKAPI
from app.services.vk_user_filter import apply_filters_to_profiles


@pytest.fixture(scope="module")
async def real_friends_data(vk_api_client: VKAPI) -> List[Dict[Any, Any]]:
    print("\n[DIAGNOSTICS_SETUP] Получение полного списка друзей от VK API...")
    try:
        response = await vk_api_client.get_user_friends(
            user_id=vk_api_client.user_id,
            fields="sex,online,last_seen,is_closed,status,deactivated,city,has_photo"
        )
        assert response and "items" in response, "Не удалось получить список друзей."
        friends = response["items"]
        print(f"[DIAGNOSTICS_SETUP] ✓ Успешно получено {len(friends)} друзей.")
        return friends
    except Exception as e:
        pytest.fail(f"Критическая ошибка при получении списка друзей: {e}")

async def test_all_fast_filters_on_live_data(real_friends_data: list):
    print(f"\n\n{'='*25} НАЧАЛО ДИАГНОСТИКИ ФИЛЬТРОВ {'='*25}")
    
    total_friends = len(real_friends_data)
    active_friends = [p for p in real_friends_data if not p.get('deactivated')]
    print(f"  - Всего друзей в аккаунте: {total_friends}")
    print(f"  - Активных (не 'собачек'): {len(active_friends)}")
    
    print("\n" + "-"*20 + " Этап 1: Тестирование каждого фильтра по отдельности " + "-"*20)
    
    async def run_single_filter_test(name: str, filters: ActionFilters):
        result = await apply_filters_to_profiles(active_friends, filters)
        print(f"  - Фильтр '{name}': Найдено {len(result)} чел.")

    # Создаем базовый фильтр, который разрешает закрытые профили для чистоты тестов
    base_filters = ActionFilters(allow_closed_profiles=True)

    await run_single_filter_test("Пол: Женский", base_filters.model_copy(update={"sex": 1}))
    await run_single_filter_test("Пол: Мужской", base_filters.model_copy(update={"sex": 2}))
    await run_single_filter_test("Сейчас онлайн", base_filters.model_copy(update={"is_online": True}))
    await run_single_filter_test("Был онлайн последние 24 часа", base_filters.model_copy(update={"last_seen_hours": 24}))
    await run_single_filter_test("Есть аватар", base_filters.model_copy(update={"only_with_photo": True})) # only_with_photo не входит в стандартный набор полей, но для теста добавим
    await run_single_filter_test("Статус содержит 'любовь'", base_filters.model_copy(update={"status_keyword": "любовь"}))
    await run_single_filter_test("Город: Москва", base_filters.model_copy(update={"city": "Москва"}))
    await run_single_filter_test("Забаненные/удаленные", ActionFilters(remove_banned=True))

    print("\n" + "-"*20 + " Этап 2: Тестирование комбинаций " + "-"*20)
    
    combo_filters = ActionFilters(
        allow_closed_profiles=True,
        sex=1,
        is_online=True,
        city="Москва"
    )
    await run_single_filter_test("Комбо: Женщины, онлайн, из Москвы", combo_filters)
    
    print(f"\n{'='*25} ДИАГНОСТИКА ФИЛЬТРОВ ЗАВЕРШЕНА {'='*25}")