# tests/admin/test_admin_auth.py

import pytest
from httpx import AsyncClient

from app.db.models import User
from app.core.config import settings

pytestmark = pytest.mark.anyio

async def test_non_admin_cannot_access_admin_panel(
    async_client: AsyncClient, test_user: User, auth_headers: dict
):
    """
    Тест: Обычный пользователь не может получить доступ к админ-панели.
    Его должно перенаправить на страницу логина.
    """
    # Act: Пытаемся зайти на страницу пользователей в админке
    response = await async_client.get("/admin/user/list", headers=auth_headers, follow_redirects=False)

    # Assert: Ожидаем редирект (код 307)
    assert response.status_code == 302
    assert "/admin/login" in response.headers["location"]

async def test_admin_can_login_and_access_panel(
    async_client: AsyncClient, db_session, admin_user: User
):
    """
    Тест: Пользователь-администратор может успешно залогиниться и получить
    доступ к защищенной странице админ-панели.
    """
    # Act (Phase 1): Логинимся в админку
    login_data = {
        "username": settings.ADMIN_USER,
        "password": settings.ADMIN_PASSWORD
    }
    response_login = await async_client.post("/admin/login", data=login_data, follow_redirects=False)

    # Assert (Phase 1): Проверяем успешный редирект после логина
    assert response_login.status_code == 302
    assert "/admin/user/list" in response_login.headers["location"]
    
    # httpx клиент автоматически сохраняет и использует куки сессии
    
    # Act (Phase 2): Заходим на страницу пользователей
    response_list = await async_client.get("/admin/user/list")

    # Assert (Phase 2): Проверяем, что доступ получен (код 200)
    assert response_list.status_code == 200
    assert f"<h1>Пользователи</h1>" in response_list.text