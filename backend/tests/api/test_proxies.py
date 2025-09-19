# tests/api/test_proxies.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
# --- ИЗМЕНЕНИЕ: Добавляем импорт Plan ---
from sqlalchemy import select, func

# --- ИЗМЕНЕНИЕ: Добавляем импорт Plan и PlanName ---
from app.db.models import User, Proxy, Plan
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
    
    # --- НАЧАЛО ИСПРАВЛЕНИЯ (ОШИБКА MissingGreenlet) ---
    # Обновляем объект test_user, чтобы он "увидел" новый прокси.
    # Это ключевой шаг для избежания ошибок ленивой загрузки.
    await db_session.refresh(test_user, attribute_names=['proxies'])
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

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
    # --- НАЧАЛО ИСПРАВЛЕНИЯ (ОШИБКА AttributeError) ---
    # 1. Находим в БД объект базового тарифа
    base_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.BASE.name))).scalar_one()
    # 2. Присваиваем ID этого тарифа в поле-внешний ключ
    test_user.plan_id = base_plan.id
    await db_session.commit()
    # 3. Обновляем объект, чтобы подтянулась новая связь
    await db_session.refresh(test_user, ['plan'])
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    response = await async_client.post(
        "/api/v1/proxies", headers=auth_headers, json={"proxy_url": "http://some.proxy"}
    )

    assert response.status_code == 403
    assert "доступно только на PRO-тарифе" in response.json()["detail"]

async def test_delete_another_users_proxy(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест безопасности: пользователь не может удалить прокси, принадлежащий другому пользователю.
    """
    # Arrange: Создаем второго пользователя и его прокси
    other_user = User(vk_id=999, encrypted_vk_token="other")
    db_session.add(other_user)
    await db_session.flush()
    other_proxy = Proxy(user_id=other_user.id, encrypted_proxy_url="secret_url")
    db_session.add(other_proxy)
    await db_session.commit()
    
    # Act: Пытаемся удалить чужой прокси под своими учетными данными
    response = await async_client.delete(f"/api/v1/proxies/{other_proxy.id}", headers=auth_headers)

    # Assert: Ожидаем ошибку 404, так как для нас этого прокси "не существует"
    assert response.status_code == 404