# backend/Dockerfile

# --- STAGE 1: Build venv ---
FROM python:3.11-slim-bookworm AS builder

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

RUN pip install --upgrade pip && pip install poetry
# Эта команда гарантирует, что .venv создастся в /app/
RUN poetry config virtualenvs.in-project true

COPY poetry.lock pyproject.toml ./

RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --no-root --without dev


# --- STAGE 2: Final Image ---
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Это ключевая строка, она "активирует" наше окружение
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# --- ИСПРАВЛЕНИЕ: 'pip install poetry' здесь больше не нужен ---
COPY --from=builder /app/.venv /app/.venv

COPY ./app /app/app
COPY ./alembic.ini /app/
COPY ./migrations /app/migrations
COPY ./pyproject.toml /app/
COPY ./poetry.lock /app/

RUN useradd --create-home appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000