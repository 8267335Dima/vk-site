# tests/api/test_support.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, SupportTicket, TicketMessage

pytestmark = pytest.mark.anyio


async def test_support_ticket_lifecycle(async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    """
    Тестирует полный жизненный цикл тикета: создание, получение, ответ.
    """
    # 1. Создание тикета
    create_data = {
        "subject": "Проблема с оплатой",
        "message": "Не проходит платеж по карте."
    }
    response_create = await async_client.post("/api/v1/support", headers=auth_headers, json=create_data)

    assert response_create.status_code == 201
    created_ticket_data = response_create.json()
    ticket_id = created_ticket_data["id"]
    assert created_ticket_data["subject"] == "Проблема с оплатой"
    assert len(created_ticket_data["messages"]) == 1
    assert created_ticket_data["messages"][0]["message"] == "Не проходит платеж по карте."

    # 2. Получение деталей созданного тикета
    response_get = await async_client.get(f"/api/v1/support/{ticket_id}", headers=auth_headers)
    assert response_get.status_code == 200
    assert response_get.json()["id"] == ticket_id

    # 3. Ответ на тикет
    reply_data = {"message": "Я попробовал еще раз, все равно ошибка."}
    response_reply = await async_client.post(f"/api/v1/support/{ticket_id}/messages", headers=auth_headers, json=reply_data)

    assert response_reply.status_code == 200
    replied_ticket_data = response_reply.json()
    assert len(replied_ticket_data["messages"]) == 2
    assert replied_ticket_data["messages"][1]["message"] == "Я попробовал еще раз, все равно ошибка."

    # Проверка в БД
    ticket_in_db = await db_session.get(SupportTicket, ticket_id)
    await db_session.refresh(ticket_in_db, attribute_names=['messages'])
    assert len(ticket_in_db.messages) == 2


async def test_cannot_access_other_user_ticket(async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """
    Тест проверяет, что пользователь не может получить доступ к тикету другого пользователя.
    """
    # Arrange: Создаем другого пользователя и его тикет
    other_user = User(vk_id=999888, encrypted_vk_token="other_token")
    db_session.add(other_user)
    await db_session.flush()
    other_ticket = SupportTicket(user_id=other_user.id, subject="Чужой тикет")
    db_session.add(other_ticket)
    await db_session.commit()

    # Act: Пытаемся получить доступ к чужому тикету
    response = await async_client.get(f"/api/v1/support/{other_ticket.id}", headers=auth_headers)

    # Assert
    assert response.status_code == 404