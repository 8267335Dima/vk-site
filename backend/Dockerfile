# --- STAGE 1: Build venv with all dependencies ---
FROM python:3.11-slim-bookworm AS builder

# Устанавливаем переменные окружения для Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

# Устанавливаем Poetry
RUN pip install --upgrade pip && pip install poetry

# Копируем файлы зависимостей
COPY poetry.lock pyproject.toml ./
RUN poetry config repositories.pypi https://pypi.org/simple/
# --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ---
# Добавлен флаг '--with dev', чтобы установить ВСЕ зависимости,
# включая pytest, httpx и asgi-lifespan.
RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --no-root --with dev


# --- STAGE 2: Final Production Image ---
FROM python:3.11-slim-bookworm

# Устанавливаем переменные окружения для Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Указываем Python, где искать наши установленные пакеты
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Копируем готовое виртуальное окружение из builder-стадии
COPY --from=builder /app/.venv /app/.venv

# Копируем весь код проекта одной командой.
COPY . /app/

# Создаем непривилегированного пользователя для запуска приложения.
RUN useradd --create-home appuser && \
    chown -R appuser:appuser /app

# Переключаемся на этого пользователя
USER appuser

# Открываем порт, на котором будет работать приложение