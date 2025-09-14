import json
import pytest
from httpx import AsyncClient
from app.core.config import settings

# Стандартная практика для pytest-asyncio, помечает все тесты в файле как асинхронные
pytestmark = pytest.mark.asyncio

# ----------------------------- ВСПОМОГАТЕЛЬНЫЕ ДАННЫЕ И ФУНКЦИИ -----------------------------

# Базовый payload для создания сценария. Используется как отправная точка.
BASE_PAYLOAD = {
    "name": "Сценарий, созданный тестом",
    "schedule": "0 12 * * *",
    "is_active": True,
    "nodes": [
        {
            "id": "node-1",
            "type": "start",
            "position": {"x": 100, "y": 100},
            "data": {}
        }
    ],
    "edges": []
}

def pretty(obj):
    """Утилита для красивого вывода JSON в консоль для отладки."""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)

async def login_and_headers(client: AsyncClient) -> dict:
    """Выполняет логин через тестовый VK токен и возвращает заголовки для авторизации."""
    test_token = settings.VK_HEALTH_CHECK_TOKEN
    assert test_token, "Переменная VK_HEALTH_CHECK_TOKEN должна быть в .env файле"

    r = await client.post("/api/v1/auth/vk", json={"vk_token": test_token})
    assert r.status_code == 200, f"Не удалось залогиниться. Статус: {r.status_code}, Тело: {r.text}"
    
    access_token = r.json().get("access_token")
    assert access_token, f"В ответе на логин отсутствует access_token: {r.text}"
    
    return {"Authorization": f"Bearer {access_token}"}

async def create_scenario(client: AsyncClient, headers: dict, payload: dict) -> dict:
    """Отправляет запрос на создание сценария и проверяет успешность."""
    r = await client.post("/api/v1/scenarios", headers=headers, json=payload)
    assert r.status_code == 201, f"Ошибка создания. Ожидался статус 201, получен {r.status_code}. Тело: {r.text}"
    return r.json()

async def fetch_scenario(client: AsyncClient, headers: dict, scenario_id: int) -> dict:
    """Отправляет запрос на получение сценария по ID и проверяет успешность."""
    r = await client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
    assert r.status_code == 200, f"Ошибка получения. Ожидался статус 200, получен {r.status_code}. Тело: {r.text}"
    return r.json()

async def update_scenario(client: AsyncClient, headers: dict, scenario_id: int, payload: dict) -> dict:
    """Отправляет запрос на обновление сценария и проверяет успешность."""
    r = await client.put(f"/api/v1/scenarios/{scenario_id}", headers=headers, json=payload)
    assert r.status_code == 200, f"Ошибка обновления. Ожидался статус 200, получен {r.status_code}. Тело: {r.text}"
    return r.json()

async def delete_scenario(client: AsyncClient, headers: dict, scenario_id: int):
    """Отправляет запрос на удаление сценария и проверяет успешность."""
    r = await client.delete(f"/api/v1/scenarios/{scenario_id}", headers=headers)
    assert r.status_code == 204, f"Ошибка удаления. Ожидался статус 204, получен {r.status_code}. Тело: {r.text}"

async def assert_nodes_match(expected_nodes: list, actual_nodes: list):
    """Сравнивает два списка узлов, игнорируя порядок, но проверяя содержимое каждого узла."""
    assert len(expected_nodes) == len(actual_nodes), \
        f"Количество узлов не совпадает. Ожидалось {len(expected_nodes)}, получено {len(actual_nodes)}\n" \
        f"Полученные узлы:\n{pretty(actual_nodes)}"

    actual_by_id = {n["id"]: n for n in actual_nodes}
    for expected_node in expected_nodes:
        node_id = expected_node["id"]
        assert node_id in actual_by_id, f"Узел с id='{node_id}' отсутствует в ответе сервера."
        
        actual_node = actual_by_id[node_id]
        assert expected_node["type"] == actual_node["type"], f"Тип узла '{node_id}' не совпадает."
        # Сравнение словарей data
        assert expected_node.get("data", {}) == actual_node.get("data", {}), f"Поле 'data' для узла '{node_id}' не совпадает."

async def assert_edges_match(expected_edges: list, actual_edges: list):
    """Сравнивает два списка связей, игнорируя порядок."""
    assert len(expected_edges) == len(actual_edges), \
        f"Количество связей не совпадает. Ожидалось {len(expected_edges)}, получено {len(actual_edges)}\n" \
        f"Полученные связи:\n{pretty(actual_edges)}"

    # Преобразуем связи в кортежи для удобного сравнения в виде множеств
    expected_set = { (e["source"], e["target"], e.get("sourceHandle")) for e in expected_edges }
    actual_set = { (e["source"], e["target"], e.get("sourceHandle")) for e in actual_edges }
    assert expected_set == actual_set, "Наборы связей (source, target, sourceHandle) не совпадают."


# ----------------------------- ОСНОВНОЙ ТЕСТ ЖИЗНЕННОГО ЦИКЛА -----------------------------

async def test_full_scenario_lifecycle(async_client: AsyncClient, authorized_user_and_headers: tuple):
    """
    Тестирует полный жизненный цикл сценария...
    """
    print("\n--- Начало теста жизненного цикла сценария ---")
    user, headers = authorized_user_and_headers

    # --- 1. CREATE ---
    print("\n[1] Создание сценария...")
    created_scenario = await create_scenario(async_client, headers, BASE_PAYLOAD)
    print("Ответ сервера (CREATE):\n", pretty(created_scenario))
    
    scenario_id = created_scenario["id"]
    assert created_scenario["name"] == BASE_PAYLOAD["name"]
    assert created_scenario["is_active"] == BASE_PAYLOAD["is_active"]
    await assert_nodes_match(BASE_PAYLOAD["nodes"], created_scenario.get("nodes", []))
    await assert_edges_match(BASE_PAYLOAD["edges"], created_scenario.get("edges", []))
    print("✓ Создание успешно и данные корректны.")

    # --- 2. FETCH (сразу после создания) ---
    print(f"\n[2] Получение сценария по id={scenario_id}...")
    fetched_scenario = await fetch_scenario(async_client, headers, scenario_id)
    print("Ответ сервера (FETCH):\n", pretty(fetched_scenario))
    
    assert fetched_scenario["id"] == scenario_id
    assert fetched_scenario["name"] == BASE_PAYLOAD["name"]
    print("✓ Полученные данные консистентны.")

    # --- 3. UPDATE ---
    print(f"\n[3] Обновление сценария id={scenario_id}...")
    update_payload = {
        "name": "Сценарий, обновлённый тестом",
        "schedule": "30 14 * * 1-5",
        "is_active": False,
        "nodes": [
            {"id": "node-1", "type": "start", "position": {"x": 100, "y": 100}, "data": {}},
            {"id": "node-2", "type": "action", "position": {"x": 300, "y": 100}, "data": {"action_type": "like_feed"}},
            {"id": "node-3", "type": "condition", "position": {"x": 500, "y": 100}, "data": {"metric": "day_of_week"}},
            {"id": "node-4", "type": "action", "position": {"x": 700, "y": 0}, "data": {"action_type": "add_recommended"}},
            {"id": "node-5", "type": "action", "position": {"x": 700, "y": 200}, "data": {"action_type": "view_stories"}}
        ],
        "edges": [
            {"id": "e1-2", "source": "node-1", "target": "node-2", "sourceHandle": None},
            {"id": "e2-3", "source": "node-2", "target": "node-3", "sourceHandle": None},
            {"id": "e3-4", "source": "node-3", "target": "node-4", "sourceHandle": "on_success"},
            {"id": "e3-5", "source": "node-3", "target": "node-5", "sourceHandle": "on_failure"}
        ]
    }
    updated_scenario = await update_scenario(async_client, headers, scenario_id, update_payload)
    print("Ответ сервера (UPDATE):\n", pretty(updated_scenario))
    
    assert updated_scenario["name"] == update_payload["name"]
    assert updated_scenario["is_active"] is False
    await assert_nodes_match(update_payload["nodes"], updated_scenario.get("nodes", []))
    await assert_edges_match(update_payload["edges"], updated_scenario.get("edges", []))
    print("✓ Обновление успешно и данные в ответе корректны.")

    # --- 4. FETCH (после обновления) ---
    print(f"\n[4] Повторное получение сценария id={scenario_id} для проверки сохранения...")
    fetched_after_update = await fetch_scenario(async_client, headers, scenario_id)
    assert fetched_after_update["name"] == update_payload["name"], "Имя не сохранилось после обновления"
    assert fetched_after_update["is_active"] is False, "Статус активности не сохранился"
    await assert_nodes_match(update_payload["nodes"], fetched_after_update.get("nodes", []))
    await assert_edges_match(update_payload["edges"], fetched_after_update.get("edges", []))
    print("✓ Данные успешно сохранены в БД.")

    # --- 5. DELETE ---
    print(f"\n[5] Удаление сценария id={scenario_id}...")
    await delete_scenario(async_client, headers, scenario_id)
    print("✓ Запрос на удаление успешен.")

    # --- 6. VERIFY DELETION ---
    print(f"\n[6] Проверка, что сценарий id={scenario_id} действительно удален...")
    r = await async_client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
    assert r.status_code == 404, f"После удаления GET должен возвращать 404, но вернул {r.status_code}"
    print("✓ Сценарий удален (GET вернул 404).")

    # --- 7. NEGATIVE CASE ---
    print("\n[7] Негативный тест: создание сценария с неверным CRON...")
    bad_payload = {**BASE_PAYLOAD, "schedule": "this-is-not-a-valid-cron-string"}
    r_bad = await async_client.post("/api/v1/scenarios", headers=headers, json=bad_payload)
    assert r_bad.status_code == 400, f"Ожидался статус 400, получен {r_bad.status_code}"
    assert "CRON" in r_bad.json().get("detail", ""), "В сообщении об ошибке не упоминается CRON"
    print("✓ Сервер вернул ошибку 400 на невалидный CRON.")

    print("\n--- Тест жизненного цикла сценария успешно завершен! ---")