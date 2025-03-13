from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# Базовая схема пользователя
class UserBase(BaseModel):
    name: str
    email: EmailStr


# Схема для создания пользователя
class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


# Схема для обновления пользователя
class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None


# Схема для ответа с полной информацией о пользователе
class UserResponse(UserBase):
    id: UUID
    created_at: datetime

    class Config:
        orm_mode = True


# Схема для токена доступа
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Схема данных токена
class TokenData(BaseModel):
    user_id: UUID 