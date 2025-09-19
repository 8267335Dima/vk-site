# tests/api/test_dependencies.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.api.dependencies import get_current_active_profile
from app.db.models import User

pytestmark = pytest.mark.anyio

async def test_get_active_profile_without_profile_id_in_token(db_session: AsyncSession, test_user: User):
    """
    Тест: если в токене нет 'profile_id', функция должна вернуть пользователя
    из поля 'sub' (т.е. самого менеджера).
    """
    # Arrange
    payload = {"sub": str(test_user.id)}

    # Act
    active_profile = await get_current_active_profile(payload=payload, db=db_session)

    # Assert
    assert active_profile is not None
    assert active_profile.id == test_user.id

async def test_get_active_profile_with_valid_profile_id(
    db_session: AsyncSession, manager_user: User, managed_profile_user: User
):
    """
    Тест: если в токене есть 'profile_id', функция должна вернуть
    именно этот профиль.
    """
    # Arrange
    payload = {
        "sub": str(manager_user.id),
        "profile_id": str(managed_profile_user.id)
    }

    # Act
    active_profile = await get_current_active_profile(payload=payload, db=db_session)

    # Assert
    assert active_profile is not None
    assert active_profile.id == managed_profile_user.id

async def test_get_active_profile_with_non_existent_profile_id(
    db_session: AsyncSession, manager_user: User
):
    """
    Тест (безопасность): функция должна выбросить исключение, если 'profile_id'
    указывает на несуществующего пользователя.
    """
    # Arrange
    non_existent_id = 999999
    payload = {
        "sub": str(manager_user.id),
        "profile_id": str(non_existent_id)
    }

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_profile(payload=payload, db=db_session)
    
    assert exc_info.value.status_code == 404
    assert "Активный профиль не найден" in exc_info.value.detail