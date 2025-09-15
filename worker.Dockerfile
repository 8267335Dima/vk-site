# Используем тот же базовый образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем переменные окружения для Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry'

# Устанавливаем Poetry
RUN pip install poetry

# Копируем только файлы зависимостей, чтобы использовать кэш Docker
COPY ./backend/poetry.lock ./backend/pyproject.toml ./

# Устанавливаем зависимости проекта. Этот слой будет кэшироваться,
# если файлы зависимостей не менялись.
# --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
RUN poetry install --no-root --without dev

# Копируем весь остальной код приложения
COPY ./backend .

# Команда, которая будет выполняться при запуске контейнера
CMD ["python", "-m", "arq", "--watch", ".", "app.worker.WorkerSettings"]