# tests/services/test_vk_user_filter.py
import pytest
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import ActionFilters

pytestmark = pytest.mark.asyncio

# Пример данных, которые мог бы вернуть VK API
mock_profiles = [
    {"id": 1, "sex": 2, "online": 1, "city": {"title": "Москва"}}, # Мужчина, онлайн, Москва
    {"id": 2, "sex": 1, "online": 0, "city": {"title": "Москва"}}, # Женщина, оффлайн, Москва
    {"id": 3, "sex": 2, "online": 1, "city": {"title": "Санкт-Петербург"}}, # Мужчина, онлайн, СПб
    {"id": 4, "sex": 1, "online": 1, "city": {"title": "Москва"}}, # Женщина, онлайн, Москва
    {"id": 5, "deactivated": "banned"}, # Забаненный
]

async def test_filter_by_sex():
    filters = ActionFilters(sex=1) # Только женщины
    result = await apply_filters_to_profiles(mock_profiles, filters)
    assert len(result) == 2
    assert {p["id"] for p in result} == {2, 4}

async def test_filter_by_online():
    filters = ActionFilters(is_online=True)
    result = await apply_filters_to_profiles(mock_profiles, filters)
    assert len(result) == 3
    assert {p["id"] for p in result} == {1, 3, 4}

async def test_filter_by_city():
    filters = ActionFilters(city="Москва")
    result = await apply_filters_to_profiles(mock_profiles, filters)
    assert len(result) == 3
    assert {p["id"] for p in result} == {1, 2, 4}

async def test_complex_filter():
    # Женщины, онлайн, из Москвы
    filters = ActionFilters(sex=1, is_online=True, city="Москва")
    result = await apply_filters_to_profiles(mock_profiles, filters)
    assert len(result) == 1
    assert result[0]["id"] == 4

async def test_remove_banned_filter():
    # Фильтр на удаление забаненных
    filters = ActionFilters(remove_banned=True)
    result = await apply_filters_to_profiles(mock_profiles, filters)
    # Забаненный должен остаться в списке, так как фильтр remove_banned не исключает, а является условием для действия
    assert len(result) == 5