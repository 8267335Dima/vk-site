# backend/app/db/base.py

from sqlalchemy.orm import declarative_base

# Базовый класс для всех моделей SQLAlchemy
Base = declarative_base()