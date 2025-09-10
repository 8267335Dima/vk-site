# backend/app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from cryptography.fernet import Fernet
from app.core.config import settings

try:
    cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())
except Exception:
    raise ValueError("Invalid ENCRYPTION_KEY in .env file. Please generate a valid Fernet key.")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def encrypt_data(data: Optional[str]) -> Optional[str]:
    """Шифрует строку с использованием Fernet, обрабатывает None."""
    if data is None:
        return None
    return cipher_suite.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: Optional[str]) -> Optional[str]:
    """Дешифрует строку с использованием Fernet, обрабатывает None."""
    if encrypted_data is None:
        return None
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except Exception:
        # В случае невалидных данных возвращаем None
        return None