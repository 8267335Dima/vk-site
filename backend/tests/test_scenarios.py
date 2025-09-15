# backend/tests/test_scenarios.py (Полная новая версия)
import pytest
from httpx import AsyncClient
import json

pytestmark = pytest.mark.asyncio

# --- Сложный payload для создания сценария с ветвлением ---
COMPLEX_PAYLOAD = {
    "name": "Тестовый сценарий с ветвлением",
    "schedule": "0 8 * * 1-5", # Каждый будний день в 8 утра
    "is_active": True,
    "nodes": [
        {"id": "node-start", "type": "start", "position": {"x": 50, "y": 200}, "data": {}},
        {"id": "node-like", "type": "action", "position": {"x": 250, "y": 200}, "data": {"action_type": "like_feed", "settings": {"count": 25}}},
        {"id": "node-check-day", "type": "condition", "position": {"x": 500, "y": 200}, "data": {"metric": "day_of_week", "operator": "==", "value": "5"}},
        {"id": "node-add-friends", "type": "action", "position": {"x": 750, "y": 100}, "data": {"action_type": "add_recommended", "settings": {"count": 10}}},
        {"id": "node-view-stories", "type": "action", "position": {"x": 750, "y": 300}, "data": {"action_type": "view_stories", "settings": {}}}
    ],
    "edges": [
        {"id": "e-start-like", "source": "node-start", "target": "node-like"},
        {"id": "e-like-check", "source": "node-like", "target": "node-check-day"},
        {"id": "e-check-add", "source": "node-check-day", "target": "node-add-friends", "sourceHandle": "on_success"},
        {"id": "e-check-view", "source": "node-check-day", "target": "node-view-stories", "sourceHandle": "on_failure"}
    ]
}

def pretty_print(data):
    return json.dumps(data, indent=2, ensure_ascii=False)

async def test_full_scenario_lifecycle(async_client: AsyncClient, authorized_user_and_headers: tuple):
    _, headers = authorized_user_and_headers
    scenario_id = None
    
    try:
        # --- 1. CREATE ---
        print("\n[SCENARIO TEST - 1] Создание сложного сценария...")
        response = await async_client.post("/api/v1/scenarios", headers=headers, json=COMPLEX_PAYLOAD)
        assert response.status_code == 201, f"Ошибка создания: {response.text}"
        created_scenario = response.json()
        scenario_id = created_scenario["id"]
        print(f"✓ Сценарий создан, ID: {scenario_id}")
        assert len(created_scenario['nodes']) == 5
        assert len(created_scenario['edges']) == 4

        # --- 2. FETCH and VERIFY ---
        print("\n[SCENARIO TEST - 2] Получение и проверка созданного сценария...")
        response = await async_client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
        assert response.status_code == 200
        fetched_scenario = response.json()
        assert fetched_scenario['name'] == COMPLEX_PAYLOAD['name']
        assert fetched_scenario['edges'][2]['sourceHandle'] == 'on_success' # Проверяем одну из связей
        print("✓ Данные созданного сценария корректны.")

        # --- 3. UPDATE ---
        print("\n[SCENARIO TEST - 3] Обновление сценария (меняем имя и деактивируем)...")
        update_payload = COMPLEX_PAYLOAD.copy()
        update_payload['name'] = "Обновленный тестовый сценарий"
        update_payload['is_active'] = False
        response = await async_client.put(f"/api/v1/scenarios/{scenario_id}", headers=headers, json=update_payload)
        assert response.status_code == 200, f"Ошибка обновления: {response.text}"
        updated_scenario = response.json()
        assert updated_scenario['name'] == "Обновленный тестовый сценарий"
        assert updated_scenario['is_active'] is False
        print("✓ Сценарий успешно обновлен.")

        # --- 4. FETCH after UPDATE ---
        print("\n[SCENARIO TEST - 4] Проверка сохранения обновленных данных...")
        response = await async_client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
        assert response.status_code == 200
        fetched_after_update = response.json()
        assert fetched_after_update['name'] == "Обновленный тестовый сценарий"
        assert fetched_after_update['is_active'] is False
        print("✓ Обновленные данные корректно сохранены в БД.")

    finally:
        # --- 5. DELETE ---
        if scenario_id:
            print(f"\n[SCENARIO TEST - 5] Удаление тестового сценария ID: {scenario_id}...")
            response = await async_client.delete(f"/api/v1/scenarios/{scenario_id}", headers=headers)
            assert response.status_code == 204
            print("✓ Сценарий удален.")
            
            # --- 6. VERIFY DELETION ---
            response = await async_client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
            assert response.status_code == 404
            print("✓ Проверка удаления (404) пройдена.")