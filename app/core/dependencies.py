from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.services.user_service import UserService


# Зависимости для сервисов
async def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


async def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)


async def get_message_service(db: AsyncSession = Depends(get_db)) -> MessageService:
    return MessageService(db) 