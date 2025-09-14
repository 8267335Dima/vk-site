import json
import pytest
from httpx import AsyncClient
from app.core.config import settings

pytestmark = pytest.mark.asyncio

# Базовый payload для создания
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
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)


def assert_eq_or_dump(expected, actual, message):
    """Утилита: assert с удобным выводом expected/actual при ошибке."""
    assert expected == actual, f"{message}\nEXPECTED:\n{pretty(expected)}\nACTUAL:\n{pretty(actual)}"


def find_edge(edges, source, target, sourceHandle=None):
    for e in edges:
        if e.get("source") == source and e.get("target") == target:
            if sourceHandle is None:
                return e
            # sourceHandle may be "on_success"/"on_failure"
            if e.get("sourceHandle") == sourceHandle:
                return e
    return None


async def login_and_headers(client: AsyncClient):
    """Логинимся через VK-Health token (как в проекте) и возвращаем headers."""
    test_token = settings.VK_HEALTH_CHECK_TOKEN
    assert test_token, "Переменная VK_HEALTH_CHECK_TOKEN должна быть в .env"

    r = await client.post("/api/v1/auth/vk", json={"vk_token": test_token})
    if r.status_code != 200:
        raise AssertionError(f"Не удалось залогиниться. status={r.status_code}, body={r.text}")
    access_token = r.json().get("access_token")
    assert access_token, f"В ответе нет access_token: {r.text}"
    return {"Authorization": f"Bearer {access_token}"}


async def create_scenario(client: AsyncClient, headers: dict, payload: dict):
    r = await client.post("/api/v1/scenarios", headers=headers, json=payload)
    if r.status_code != 201:
        # print детально тело ошибки для отладки
        print("CREATE FAILED: status =", r.status_code)
        print("RESPONSE BODY:", r.text)
    assert r.status_code == 201, f"Create failed: status={r.status_code}, body={r.text}"
    return r.json()


async def fetch_scenario(client: AsyncClient, headers: dict, scenario_id: int):
    r = await client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
    if r.status_code != 200:
        print("GET FAILED: status =", r.status_code)
        print("RESPONSE BODY:", r.text)
    assert r.status_code == 200, f"Fetch failed: status={r.status_code}, body={r.text}"
    return r.json()


async def update_scenario(client: AsyncClient, headers: dict, scenario_id: int, payload: dict):
    r = await client.put(f"/api/v1/scenarios/{scenario_id}", headers=headers, json=payload)
    if r.status_code != 200:
        print("UPDATE FAILED: status =", r.status_code)
        print("RESPONSE BODY:", r.text)
    assert r.status_code == 200, f"Update failed: status={r.status_code}, body={r.text}"
    return r.json()


async def delete_scenario(client: AsyncClient, headers: dict, scenario_id: int):
    r = await client.delete(f"/api/v1/scenarios/{scenario_id}", headers=headers)
    if r.status_code not in (200, 204):
        print("DELETE FAILED: status =", r.status_code)
        print("RESPONSE BODY:", r.text)
    assert r.status_code in (200, 204), f"Delete failed: status={r.status_code}, body={r.text}"


async def assert_nodes_match(expected_nodes, actual_nodes):
    """
    Сопоставляем узлы по id: проверяем type/position/data наличе и соответствие.
    Удобные сообщения об ошибках, чтобы знать, что именно не совпало.
    """
    # ожидаемая и реальная длина
    assert len(expected_nodes) == len(actual_nodes), (
        f"Количество узлов не совпадает. expected={len(expected_nodes)}, actual={len(actual_nodes)}\n"
        f"actual_nodes:\n{pretty(actual_nodes)}"
    )

    # создадим маппинг actual по id
    actual_by_id = {n["id"]: n for n in actual_nodes}

    for exp in expected_nodes:
        eid = exp["id"]
        assert eid in actual_by_id, f"Узел с id={eid} отсутствует во входящих nodes: {pretty(actual_nodes)}"
        act = actual_by_id[eid]

        # тип: фронт ожидает 'start'/'action'/'condition'
        assert exp["type"] == act["type"], f"Type mismatch for node {eid}: expected={exp['type']} actual={act['type']}"

        # position: сравниваем координаты (возможны float/int)
        exp_pos = exp.get("position", {})
        act_pos = act.get("position", {})
        # допускаем небольшую погрешность при сравнении чисел
        for k in ("x", "y"):
            assert k in exp_pos and k in act_pos, f"Position key {k} missing for node {eid}. exp={exp_pos}, act={act_pos}"
            assert float(exp_pos[k]) == float(act_pos[k]), (
                f"Position {k} mismatch for node {eid}: expected={exp_pos[k]}, actual={act_pos[k]}"
            )

        # data: просто проверим, что поля присутствуют (а не строгий equals, т.к. backend может дополнять)
        exp_data = exp.get("data", {})
        act_data = act.get("data", {})
        # for keys in expected data check exists and equal
        for dk, dv in exp_data.items():
            assert dk in act_data, f"Data key '{dk}' missing in node {eid}: actual_data={act_data}"
            assert act_data[dk] == dv, f"Data value mismatch for node {eid} key {dk}: expected={dv}, actual={act_data[dk]}"


async def assert_edges_match(expected_edges, actual_edges):
    """
    Проверяем наличие ожидаемых ребер (по source,target и sourceHandle если указан).
    Не обязательно порядок.
    """
    for exp in expected_edges:
        src = exp["source"]
        tgt = exp["target"]
        sh = exp.get("sourceHandle")
        found = find_edge(actual_edges, src, tgt, sh)
        assert found is not None, f"Edge not found: source={src} target={tgt} sourceHandle={sh}\nactual_edges:\n{pretty(actual_edges)}"


# ----------------------------- НАИБОЛЕЕ ПОДРОБНЫЙ end-to-end тест -----------------------------
async def test_full_scenario_lifecycle(async_client: AsyncClient):
    """
    Полный сценарий теста:
    1) логинимся
    2) создаём минимальный сценарий (start)
    3) проверяем тело ответа
    4) GET по id — проверяем, что данные совпадают
    5) обновляем сценарий: добавляем action и condition + ребра (on_success/on_failure)
    6) проверяем тело ответа после UPDATE и снова GET
    7) удаляем сценарий и убеждаемся, что GET -> 404
    8) отрицательный кейс: попытка создать сценария с некорректным cron -> 400
    """
    client = async_client

    headers = await login_and_headers(client)

    # ---------------- CREATE ----------------
    created = await create_scenario(client, headers, BASE_PAYLOAD)
    print("CREATE RESPONSE BODY:\n", pretty(created))

    # basic checks
    assert "id" in created, f"В ответе нет id: {pretty(created)}"
    scenario_id = created["id"]
    assert created["name"] == BASE_PAYLOAD["name"], "Имя сценария в ответе не совпадает"
    assert created["schedule"] == BASE_PAYLOAD["schedule"], "CRON в ответе не совпадает"
    assert created["is_active"] is True, "is_active ожидалось True"

    # nodes check (create payload had single start node)
    assert len(created.get("nodes", [])) == 1, f"Ожидался 1 узел после создания, получили: {pretty(created.get('nodes'))}"
    assert created["nodes"][0]["type"] == "start", f"Ожидался тип узла 'start', получили: {created['nodes'][0].get('type')}"

    # ---------------- FETCH ----------------
    fetched = await fetch_scenario(client, headers, scenario_id)
    print("FETCH RESPONSE BODY:\n", pretty(fetched))

    # проверяем соответствие ключевых полей
    assert fetched["id"] == scenario_id
    assert fetched["name"] == BASE_PAYLOAD["name"]
    assert fetched["schedule"] == BASE_PAYLOAD["schedule"]
    assert fetched["is_active"] is True

    # граф совпадает
    await assert_nodes_match(BASE_PAYLOAD["nodes"], fetched["nodes"])
    assert fetched.get("edges") == [], f"Ожидались пустые edges после создания, получили: {pretty(fetched.get('edges'))}"

    # ---------------- UPDATE (добавляем 2 узла + ребра) ----------------
    update_payload = {
        "name": "Сценарий, обновлённый тестом",
        "schedule": "30 14 * * *",
        "is_active": False,
        "nodes": [
            # оставляем старый старт
            {"id": "node-1", "type": "start", "position": {"x": 100, "y": 100}, "data": {"label": "start"}},
            # новый action
            {"id": "node-2", "type": "action", "position": {"x": 200, "y": 100}, "data": {"label": "action2"}},
            # новый condition
            {"id": "node-3", "type": "condition", "position": {"x": 300, "y": 100}, "data": {"label": "cond3"}}
        ],
        "edges": [
            # start -> action
            {"source": "node-1", "target": "node-2"},
            # action -> condition
            {"source": "node-2", "target": "node-3"},
            # condition on_success -> action (node-3 -> node-2)
            {"source": "node-3", "target": "node-2", "sourceHandle": "on_success"},
            # condition on_failure -> start (node-3 -> node-1)
            {"source": "node-3", "target": "node-1", "sourceHandle": "on_failure"}
        ]
    }

    updated = await update_scenario(client, headers, scenario_id, update_payload)
    print("UPDATE RESPONSE BODY:\n", pretty(updated))

    # проверяем, что ответ отражает изменения
    assert updated["id"] == scenario_id
    assert updated["name"] == update_payload["name"]
    assert updated["schedule"] == update_payload["schedule"]
    assert updated["is_active"] is False

    # Проверка структуры nodes/edges после update
    assert len(updated.get("nodes", [])) == 3, f"Ожидалось 3 узла после обновления, получили {len(updated.get('nodes', []))}: {pretty(updated.get('nodes'))}"
    types = sorted([n["type"] for n in updated["nodes"]])
    assert types == sorted(["start", "action", "condition"]), f"Набор типов узлов неожиданен: {types}"

    # Подробная проверка nodes (по id)
    await assert_nodes_match(update_payload["nodes"], updated["nodes"])

    # Проверка ребер: их должно быть 4 и должны присутствовать конкретные
    actual_edges = updated.get("edges", [])
    assert len(actual_edges) == 4, f"Ожидалось 4 ребра после обновления, получили {len(actual_edges)}: {pretty(actual_edges)}"
    await assert_edges_match(update_payload["edges"], actual_edges)

    # Сделаем ещё один GET и проверим консистентность
    fetched_after_update = await fetch_scenario(client, headers, scenario_id)
    print("FETCH AFTER UPDATE BODY:\n", pretty(fetched_after_update))

    assert fetched_after_update["id"] == scenario_id
    assert fetched_after_update["name"] == update_payload["name"]
    assert fetched_after_update["schedule"] == update_payload["schedule"]
    assert fetched_after_update["is_active"] is False
    await assert_nodes_match(update_payload["nodes"], fetched_after_update["nodes"])
    await assert_edges_match(update_payload["edges"], fetched_after_update.get("edges", []))

    # ---------------- DELETE ----------------
    await delete_scenario(client, headers, scenario_id)
    # После удаления GET должен вернуть 404
    r = await client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers)
    assert r.status_code == 404, f"После удаления ожидался 404, получили {r.status_code}. Body: {r.text}"

    print(f"Scenario lifecycle test completed successfully for scenario_id={scenario_id}")

    # ---------------- NEGATIVE: некорректный CRON ----------------
    bad_payload = dict(BASE_PAYLOAD)
    bad_payload["schedule"] = "this-is-not-a-cron"

    r_bad = await client.post("/api/v1/scenarios", headers=headers, json=bad_payload)
    # ожидаем 400
    assert r_bad.status_code == 400, f"Ожидался 400 при некорректном crontab, получили {r_bad.status_code}. Body: {r_bad.text}"
    body_bad = r_bad.json()
    assert "CRON" in body_bad.get("detail", "") or "CRON" in body_bad.get("detail", "").upper() or "Неверный формат" in body_bad.get("detail", ""), (
        f"Ожидалась ошибка по валидации CRON, body: {pretty(body_bad)}"
    )

    print("Negative cron validation check passed.")
