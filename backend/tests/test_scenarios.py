# backend/tests/test_scenarios.py
import pytest
from httpx import AsyncClient


COMPLEX_PAYLOAD = {
    "name": "Тестовый сценарий с ветвлением", "schedule": "0 8 * * 1-5", "is_active": True,
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

async def test_full_scenario_lifecycle(async_client: AsyncClient, authorized_user_and_headers: tuple):
    _, headers = authorized_user_and_headers
    scenario_id = None
    
    try:
        # CREATE
        resp_create = await async_client.post("/api/v1/scenarios", headers=headers, json=COMPLEX_PAYLOAD)
        assert resp_create.status_code == 201
        scenario_id = resp_create.json()["id"]

        # FETCH and VERIFY
        resp_fetch = await async_client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
        assert resp_fetch.status_code == 200
        assert resp_fetch.json()['name'] == COMPLEX_PAYLOAD['name']

        # UPDATE
        update_payload = COMPLEX_PAYLOAD.copy()
        update_payload['name'] = "Обновленный сценарий"
        resp_update = await async_client.put(f"/api/v1/scenarios/{scenario_id}", headers=headers, json=update_payload)
        assert resp_update.status_code == 200
        assert resp_update.json()['name'] == "Обновленный сценарий"

    finally:
        # DELETE
        if scenario_id:
            resp_del = await async_client.delete(f"/api/v1/scenarios/{scenario_id}", headers=headers)
            assert resp_del.status_code == 204
            
            resp_verify_del = await async_client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
            assert resp_verify_del.status_code == 404