from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models.user import User
from app.schemas.message import MessageList
from app.services.message_service import MessageService

# Создание маршрутизатора
router = APIRouter(prefix=f"{settings.API_V1_STR}/history", tags=["history"])

# Получение логгера
logger = get_logger("history_routes")


@router.get("", response_model=MessageList)
async def get_message_history(
    chat_id: Optional[UUID] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получение истории сообщений для конкретного чата
    
    Параметры:
    - chat_id: ID чата для получения истории (обязательный)
    - limit: Максимальное количество сообщений (1-100, по умолчанию 50)
    - offset: Смещение для пагинации (по умолчанию 0)
    """
    logger.info(f"Запрос истории сообщений для чата {chat_id} от пользователя {current_user.id}")
    
    if not chat_id:
        logger.warning("Запрос истории без указания ID чата")
        return MessageList(messages=[], count=0)
    
    message_service = MessageService(db)
    messages = await message_service.get_chat_history(
        user_id=current_user.id,
        chat_id=chat_id,
        limit=limit,
        offset=offset
    )
    
    return MessageList(messages=messages, count=len(messages)) 