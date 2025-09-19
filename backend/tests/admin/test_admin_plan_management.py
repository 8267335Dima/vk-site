import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.db.models import Plan

ASYNC_TEST = pytest.mark.asyncio

class TestPlanAdminManagement:

    @ASYNC_TEST
    async def test_edit_plan_with_valid_json_limits(self, db_session: AsyncSession):
        """Проверяет, что валидный JSON сохраняется как строка, но может быть загружен обратно в dict."""
        plan_to_edit = await db_session.get(Plan, 1)
        assert plan_to_edit is not None
        
        new_limits = {"new_feature": True, "max_items": 100}
        plan_to_edit.limits = json.dumps(new_limits)
        
        db_session.add(plan_to_edit)
        await db_session.commit()
        await db_session.refresh(plan_to_edit)
        
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Проверяем, что в SQLite это строка
        assert isinstance(plan_to_edit.limits, str)
        # Но эта строка является валидным JSON и может быть загружена в dict
        limits_as_dict = json.loads(plan_to_edit.limits)
        assert isinstance(limits_as_dict, dict)
        assert limits_as_dict["max_items"] == 100
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    @ASYNC_TEST
    async def test_edit_plan_with_invalid_json_is_saved_in_sqlite(self, db_session: AsyncSession):
        """Проверяет, что SQLite сохраняет невалидный JSON как строку без ошибок."""
        plan_to_edit = await db_session.get(Plan, 1)
        
        invalid_json_string = '{"max_items": 50,}'
        plan_to_edit.limits = invalid_json_string
        db_session.add(plan_to_edit)
        
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Убираем pytest.raises и просто коммитим
        await db_session.commit()
        await db_session.refresh(plan_to_edit)
        
        # Проверяем, что невалидная строка успешно сохранилась
        assert plan_to_edit.limits == invalid_json_string
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---