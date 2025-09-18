# --- backend/app/db/models/__init__.py ---

# Этот файл собирает все модели из подмодулей в один неймспейс app.db.models
# Это позволяет использовать привычный импорт: from app.db.models import User

from .analytics import *
from .payment import *
from .shared import *
from .task import *
from .user import *
from .system import *