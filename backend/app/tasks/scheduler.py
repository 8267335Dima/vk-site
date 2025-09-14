import sqlalchemy
from celery.beat import Scheduler
from celery.schedules import crontab
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import Scenario

# ВАЖНО: Celery Beat - это синхронный процесс.
# Для доступа к БД из него нам нужен СИНХРОННЫЙ драйвер SQLAlchemy.
# Мы создаем его здесь локально, он не будет мешать основному асинхронному приложению.
SYNC_DB_URL = settings.database_url.replace("+asyncpg", "")
engine = sqlalchemy.create_engine(SYNC_DB_URL)
Session = sessionmaker(bind=engine)

class DatabaseScheduler(Scheduler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.schedule_changed = True

    @property
    def schedule(self):
        """
        Это главный метод. Celery Beat вызывает его при каждом "тике".
        Он напрямую читает из БД и формирует актуальное расписание.
        """
        if not self.schedule_changed:
            return self._schedule

        self.app.log.info('Reading active scenarios from database...')
        
        # Загружаем все активные сценарии из БД
        session = Session()
        try:
            active_scenarios = session.query(Scenario).filter_by(is_active=True).all()
        finally:
            session.close()

        # Формируем расписание в формате, который понимает Celery
        new_schedule = {}
        for scenario in active_scenarios:
            try:
                minute, hour, day_of_week, day_of_month, month_of_year = scenario.schedule.split(' ')
                task_name = f"scenario-{scenario.id}"
                new_schedule[task_name] = {
                    'task': 'app.tasks.runner.run_scenario_from_scheduler',
                    'schedule': crontab(
                        minute=minute, hour=hour, day_of_week=day_of_week,
                        day_of_month=day_of_month, month_of_year=month_of_year
                    ),
                    'args': (scenario.id, scenario.user_id),
                }
            except Exception as e:
                self.app.log.error(f'Failed to parse schedule for scenario {scenario.id}: {e}')
        
        self._schedule = new_schedule
        self.schedule_changed = False # Сбрасываем флаг до следующего тика
        return self._schedule

    def sync(self):
        """Этот метод вызывается для сохранения состояния, мы просто сбрасываем кэш."""
        self._schedule = None
        self.schedule_changed = True