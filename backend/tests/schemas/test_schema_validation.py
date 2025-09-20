# tests/schemas/test_schema_validation.py

import pytest
from pydantic import ValidationError

from app.api.schemas.actions import DaySchedule

class TestSchemaValidation:

    @pytest.mark.parametrize("start_time, end_time", [
        ("09:00", "18:00"),
        ("00:00", "23:59"),
        ("12:30", "12:31"),
    ])
    def test_day_schedule_valid_times(self, start_time, end_time):
        """Тест: проверяет, что валидные временные интервалы проходят валидацию."""
        try:
            DaySchedule(is_active=True, start_time=start_time, end_time=end_time)
        except ValidationError as e:
            pytest.fail(f"Valid schedule failed validation: {e}")

    @pytest.mark.parametrize("start_time, end_time, error_message", [
        ("18:00", "09:00", "Время начала должно быть раньше времени окончания"),
        ("12:00", "12:00", "Время начала должно быть раньше времени окончания"),
        ("25:00", "26:00", "Неверный формат времени"),
        ("09:00", "9:00", "Неверный формат времени"), # Не хватает ведущего нуля
        ("09:60", "10:00", "Неверный формат времени"),
    ])
    def test_day_schedule_invalid_times(self, start_time, end_time, error_message):
        """
        Тест: проверяет, что невалидные интервалы (неверный формат, неправильная логика)
        вызывают ошибку валидации.
        """
        with pytest.raises(ValidationError) as exc_info:
            DaySchedule(is_active=True, start_time=start_time, end_time=end_time)
        
        assert error_message in str(exc_info.value)