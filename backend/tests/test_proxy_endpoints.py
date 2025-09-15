# backend/tests/test_proxy_endpoints.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.models import Proxy

pytestmark = pytest.mark.asyncio

# Пример РАБОЧЕГО прокси. Замените на свой для теста.
# Если нет рабочего, тест проверки пропустится.
VALID_PROXY = "http://user:password@host:port" 

# Заведомо НЕРАБОЧИЙ прокси
INVALID_PROXY = "http://user:pass@127.0.0.1:9999"

async def test_proxy_lifecycle(async_client: AsyncClient, authorized_user_and_headers: tuple, db_session: AsyncSession):
    """
    Полный жизненный цикл: добавление, проверка, получение, удаление.
    """
    user, headers = authorized_user_and_headers
    proxy_id = None

    try:
        # 1. Добавление невалидного прокси
        print("\n--- Тестирование прокси: Добавление невалидного прокси ---")
        resp_invalid = await async_client.post("/api/v1/proxies", headers=headers, json={"proxy_url": INVALID_PROXY})
        assert resp_invalid.status_code == 201
        data_invalid = resp_invalid.json()
        assert data_invalid['is_working'] is False, "Невалидный прокси определился как рабочий"
        print("✓ Невалидный прокси успешно добавлен и помечен как нерабочий.")
        proxy_id_invalid = data_invalid['id']


        # 2. Добавление валидного прокси (если он задан)
        if "user:password" in VALID_PROXY:
             pytest.skip("Пропущен тест с валидным прокси: введите реальные данные в VALID_PROXY")
        
        print("\n--- Тестирование прокси: Добавление валидного прокси ---")
        resp_valid = await async_client.post("/api/v1/proxies", headers=headers, json={"proxy_url": VALID_PROXY})
        assert resp_valid.status_code == 201
        data_valid = resp_valid.json()
        proxy_id = data_valid['id']
        assert data_valid['is_working'] is True, "Валидный прокси определился как нерабочий"
        print(f"✓ Валидный прокси успешно добавлен (ID: {proxy_id}) и помечен как рабочий.")


        # 3. Получение списка прокси
        print("\n--- Тестирование прокси: Получение списка ---")
        resp_list = await async_client.get("/api/v1/proxies", headers=headers)
        assert resp_list.status_code == 200
        proxies_list = resp_list.json()
        assert len(proxies_list) >= 2, "В списке должно быть как минимум 2 добавленных прокси"
        print(f"✓ Список прокси успешно получен, найдено {len(proxies_list)} прокси.")

    finally:
        # 4. Очистка (удаление)
        print("\n--- Тестирование прокси: Очистка ---")
        if proxy_id:
            resp_del_valid = await async_client.delete(f"/api/v1/proxies/{proxy_id}", headers=headers)
            assert resp_del_valid.status_code == 204
            print(f"✓ Валидный прокси (ID: {proxy_id}) удален.")
        
        if 'proxy_id_invalid' in locals():
            resp_del_invalid = await async_client.delete(f"/api/v1/proxies/{proxy_id_invalid}", headers=headers)
            assert resp_del_invalid.status_code == 204
            print(f"✓ Невалидный прокси (ID: {proxy_id_invalid}) удален.")