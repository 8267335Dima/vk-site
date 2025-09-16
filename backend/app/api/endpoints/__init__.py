# --- backend/app/api/endpoints/__init__.py ---

# Этот файл собирает все роутеры из других файлов в этой директории,
# чтобы их можно было удобно импортировать и зарегистрировать в main.py

from .auth import router as auth_router
from .users import router as users_router
from .proxies import router as proxies_router
from .stats import router as stats_router
from .automations import router as automations_router
from .billing import router as billing_router
from .analytics import router as analytics_router
from .scenarios import router as scenarios_router
from .notifications import router as notifications_router
from .posts import router as posts_router
from .teams import router as teams_router
from .websockets import router as websockets_router
from .support import router as support_router
from .tasks import router as tasks_router
from .task_history import router as task_history_router