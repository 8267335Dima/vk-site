# tests/db/test_integrity.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from datetime import date

from app.db.models import User, DailyStats, Automation

pytestmark = pytest.mark.asyncio

async def test_concurrent_daily_stats_creation_fails(
    db_session: AsyncSession, test_user: User
):
    """
    Тест имитирует гонку состояний: два процесса пытаются создать
    DailyStats для одного юзера за один день. Второй должен упасть
    из-за UNIQUE constraint в БД.
    """
    # 1. Первый процесс успешно создает запись
    stats1 = DailyStats(user_id=test_user.id, date=date.today())
    db_session.add(stats1)
    await db_session.commit()

    # 2. Второй процесс пытается создать точно такую же запись
    stats2 = DailyStats(user_id=test_user.id, date=date.today())
    db_session.add(stats2)

    # Ожидаем ошибку целостности от базы данных
    with pytest.raises(IntegrityError):
        await db_session.commit()

async def test_cannot_create_duplicate_automation(
    db_session: AsyncSession, test_user: User
):
    """
    Тест проверяет UNIQUE constraint на (user_id, automation_type).
    Нельзя создать две одинаковые автоматизации для одного пользователя.
    """
    # 1. Создаем первую автоматизацию
    auto1 = Automation(user_id=test_user.id, automation_type="like_feed")
    db_session.add(auto1)
    await db_session.commit()
    
    # 2. Пытаемся создать вторую такую же
    auto2 = Automation(user_id=test_user.id, automation_type="like_feed")
    db_session.add(auto2)

    with pytest.raises(IntegrityError):
        await db_session.commit()