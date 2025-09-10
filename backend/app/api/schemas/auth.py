# backend/app/api/schemas/auth.py
from pydantic import BaseModel

class TokenRequest(BaseModel):
    vk_token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"