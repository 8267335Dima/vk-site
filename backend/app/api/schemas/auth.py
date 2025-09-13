# backend/app/api/schemas/auth.py
from pydantic import BaseModel

class TokenRequest(BaseModel):
    vk_token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class EnrichedTokenResponse(TokenResponse):
    """
    Ответ, который также возвращает ID пользователя и активного профиля,
    чтобы избавить фронтенд от необходимости декодировать JWT.
    """
    manager_id: int
    active_profile_id: int