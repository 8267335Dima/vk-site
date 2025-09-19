# tests/tasks/logic/test_analytics_jobs_logic.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta

from app.db.models import User, DailyStats, WeeklyStats, MonthlyStats
from app.tasks.logic.analytics_jobs import _aggregate_daily_stats_async

pytestmark = pytest.mark.anyio

@pytest.fixture
async def users_with_stats(db_session: AsyncSession):
    """Фикстура создает двух пользователей со статистикой за вчера."""
    user1 = User(vk_id=101, encrypted_vk_token="1")
    user2 = User(vk_id=102, encrypted_vk_token="2")
    db_session.add_all([user1, user2])
    await db_session.flush()

    yesterday = date.today() - timedelta(days=1)
    
    stats1 = DailyStats(user_id=user1.id, date=yesterday, likes_count=10, friends_added_count=2)
    stats2 = DailyStats(user_id=user2.id, date=yesterday, likes_count=20, friends_added_count=3)
    # Статистика за позавчера, которая не должна учитываться
    stats3 = DailyStats(user_id=user1.id, date=yesterday - timedelta(days=1), likes_count=100)
    
    db_session.add_all([stats1, stats2, stats3])
    await db_session.commit()
    
    return user1, user2

async def test_aggregate_daily_stats_creates_new_records(db_session: AsyncSession, users_with_stats):
    """Тест проверяет, что агрегация создает новые недельные и месячные записи."""
    # Arrange
    user1, user2 = users_with_stats
    yesterday = date.today() - timedelta(days=1)
    week_id, month_id = yesterday.strftime('%Y-%W'), yesterday.strftime('%Y-%m')

    # Act
    await _aggregate_daily_stats_async(session=db_session)

    # Assert
    # Проверяем недельную статистику
    week_stat1 = (await db_session.execute(select(WeeklyStats).where(WeeklyStats.user_id == user1.id))).scalar_one()
    week_stat2 = (await db_session.execute(select(WeeklyStats).where(WeeklyStats.user_id == user2.id))).scalar_one()
    
    assert week_stat1.likes_count == 10
    assert week_stat1.friends_added_count == 2
    assert week_stat2.likes_count == 20

    # Проверяем месячную статистику
    month_stat1 = (await db_session.execute(select(MonthlyStats).where(MonthlyStats.user_id == user1.id))).scalar_one()
    assert month_stat1.likes_count == 10
    assert month_stat1.friends_added_count == 2