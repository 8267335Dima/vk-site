# tests/api/test_proxies.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.models import User, Proxy
from app.core.enums import PlanName
from app.core.security import decrypt_data
from datetime import datetime, UTC

pytestmark = pytest.mark.anyio


async def test_add_proxy_success(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession, mocker
):
    """
    Тест успешного добавления рабочего прокси.
    """
    mocker.patch(
        "app.api.endpoints.proxies.ProxyService.check_proxy",
        return_value=(True, "Прокси успешно работает.")
    )
    
    proxy_url = "http://user:pass@1.2.3.4:8000"
    
    response = await async_client.post("/api/v1/proxies", headers=auth_headers, json={"proxy_url": proxy_url})

    assert response.status_code == 201
    data = response.json()
    assert data["proxy_url"] == proxy_url
    assert data["is_working"] is True

    proxy_in_db = (await db_session.execute(select(Proxy))).scalar_one()
    assert decrypt_data(proxy_in_db.encrypted_proxy_url) == proxy_url


async def test_get_and_delete_proxy(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession, mocker
):
    """
    Тест получения списка прокси и последующего удаления одного из них.
    """
    new_proxy = Proxy(
        user_id=test_user.id,
        encrypted_proxy_url="encrypted_url_placeholder",
        is_working=True,
        last_checked_at=datetime.now(UTC) 
    )
    db_session.add(new_proxy)
    await db_session.flush()
    # --- НАЧАЛО ИЗМЕНЕНИЯ ---
    # Обновляем объект test_user, чтобы он "увидел" новый прокси
    await db_session.refresh(test_user)
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    mocker.patch("app.api.endpoints.proxies.decrypt_data", return_value="http://user:pass@1.2.3.4:8000")

    response_get = await async_client.get("/api/v1/proxies", headers=auth_headers)

    assert response_get.status_code == 200
    data = response_get.json()
    assert len(data) == 1
    assert data[0]["id"] == new_proxy.id
    
    response_delete = await async_client.delete(f"/api/v1/proxies/{new_proxy.id}", headers=auth_headers)

    assert response_delete.status_code == 204
    
    count = (await db_session.execute(select(func.count(Proxy.id)))).scalar_one()
    assert count == 0


async def test_proxy_access_denied_for_base_plan(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест: доступ к управлению прокси должен быть запрещен для базового тарифа.
    """
    test_user.plan = PlanName.BASE.name
    await db_session.merge(test_user)
    await db_session.flush()

    response = await async_client.post(
        "/api/v1/proxies", headers=auth_headers, json={"proxy_url": "http://some.proxy"}
    )

    assert response.status_code == 403
    assert "доступно только на PRO-тарифе" in response.json()["detail"]