from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.chat import ChatType


# Базовая схема пользователя в чате
class ChatUserBase(BaseModel):
    id: UUID
    name: str
    email: str


# Базовая схема чата
class ChatBase(BaseModel):
    name: Optional[str] = None
    type: ChatType


# Схема для создания личного чата (прямого)
class DirectChatCreate(BaseModel):
    user_id: UUID


# Схема для создания группового чата
class GroupChatCreate(BaseModel):
    name: str
    user_ids: List[UUID] = Field(..., min_items=1)


# Универсальная схема для создания чата (для API)
class ChatCreate(BaseModel):
    name: Optional[str] = None
    type: str = Field(..., description="Тип чата: 'direct' или 'group'")
    user_ids: List[UUID] = Field(..., min_items=1)


# Схема для добавления пользователя в чат
class ChatUserAdd(BaseModel):
    user_id: UUID


# Схема для ответа с информацией о пользователе в чате
class ChatUserResponse(BaseModel):
    id: UUID
    name: str
    email: str


# Схема для ответа с информацией о чате
class ChatResponse(BaseModel):
    id: UUID
    name: Optional[str]
    type: str
    created_at: datetime
    users: List[ChatUserResponse]

    class Config:
        orm_mode = True


# Схема для ответа с информацией о чате для пользователя
class UserChatResponse(BaseModel):
    id: UUID
    name: Optional[str]
    type: str
    users: List[ChatUserResponse] 