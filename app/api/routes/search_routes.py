"""
Маршруты для поиска сообщений и пользователей
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.core.performance import async_time_it
from app.core.redis import redis_manager
from app.db.database import get_db
from app.db.models.chat import Chat
from app.db.models.message import Message
from app.db.models.user import User
from app.schemas.message import MessageResponse

# Создание маршрутизатора
router = APIRouter(prefix=f"{settings.API_V1_STR}/search", tags=["search"])

# Получение логгера
logger = get_logger("search_routes")


class SearchResults:
    """Класс для работы с результатами поиска"""
    
    def __init__(self, items: List[MessageResponse], total: int, query: str):
        self.items = items
        self.total = total
        self.query = query


@router.get(
    "/messages", 
    response_model=List[MessageResponse],
    summary="Поиск сообщений",
    description="""
    Выполняет поиск сообщений по тексту, с возможностью фильтрации.
    
    Поддерживает следующие параметры:
    - `query`: Текст для поиска (минимум 3 символа)
    - `chat_id`: Поиск только в указанном чате
    - `from_date`: Поиск сообщений, отправленных после указанной даты
    - `to_date`: Поиск сообщений, отправленных до указанной даты
    - `from_user_id`: Поиск сообщений от указанного пользователя
    - `limit`: Максимальное количество результатов (по умолчанию 20)
    - `offset`: Смещение для пагинации
    
    Результаты сортируются по дате отправки (новые сначала).
    """
)
@async_time_it
async def search_messages(
    query: str = Query(..., min_length=3, description="Текст для поиска"),
    chat_id: Optional[UUID] = Query(None, description="ID чата для поиска"),
    from_date: Optional[datetime] = Query(None, description="Дата начала периода"),
    to_date: Optional[datetime] = Query(None, description="Дата окончания периода"),
    from_user_id: Optional[UUID] = Query(None, description="ID отправителя"),
    limit: int = Query(20, ge=1, le=50, description="Ограничение количества результатов"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Поиск сообщений по тексту с фильтрацией
    """
    # Кэширование результатов поиска, если параметры простые
    cache_key = None
    if not any([chat_id, from_date, to_date, from_user_id]) and limit == 20 and offset == 0:
        cache_key = f"search:message:{current_user.id}:{query}"
        cached_result = await redis_manager.cache_get(cache_key)
        if cached_result:
            logger.debug(f"Возвращены кэшированные результаты поиска для запроса: {query}")
            return cached_result
    
    # Получаем чаты пользователя
    user_chats_stmt = (
        select(Chat.id)
        .join(Chat.users)
        .where(User.id == current_user.id)
    )
    user_chats_result = await db.execute(user_chats_stmt)
    user_chat_ids = [row[0] for row in user_chats_result]
    
    if not user_chat_ids:
        return []
    
    # Формируем базовый запрос
    query_stmt = (
        select(Message)
        .where(Message.chat_id.in_(user_chat_ids))
    )
    
    # Добавляем полнотекстовый поиск по тексту сообщения
    # Здесь используется ILIKE для PostgreSQL, для других СУБД можно изменить
    query_stmt = query_stmt.where(Message.text.ilike(f"%{query}%"))
    
    # Добавляем фильтры, если они указаны
    if chat_id:
        if chat_id not in user_chat_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к указанному чату"
            )
        query_stmt = query_stmt.where(Message.chat_id == chat_id)
    
    if from_date:
        query_stmt = query_stmt.where(Message.created_at >= from_date)
    
    if to_date:
        query_stmt = query_stmt.where(Message.created_at <= to_date)
    
    if from_user_id:
        query_stmt = query_stmt.where(Message.sender_id == from_user_id)
    
    # Получаем общее количество результатов
    count_stmt = select(func.count()).select_from(query_stmt.subquery())
    count_result = await db.execute(count_stmt)
    total_count = count_result.scalar_one()
    
    # Добавляем сортировку и пагинацию
    query_stmt = (
        query_stmt
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    # Выполняем запрос
    result = await db.execute(query_stmt)
    messages = result.scalars().all()
    
    # Преобразуем результаты в схему
    message_responses = [
        MessageResponse(
            id=message.id,
            chat_id=message.chat_id,
            sender_id=message.sender_id,
            text=message.text,
            created_at=message.created_at,
            updated_at=message.updated_at,
            is_read=message.is_read,
            client_message_id=message.client_message_id,
            attachments=[]  # Вложения нужно загружать отдельно
        )
        for message in messages
    ]
    
    # Кэшируем результаты, если возможно
    if cache_key:
        await redis_manager.cache_set(cache_key, message_responses, expire_seconds=300)
        logger.debug(f"Результаты поиска для запроса '{query}' кэшированы на 5 минут")
    
    logger.info(f"Поиск сообщений по запросу '{query}' вернул {len(message_responses)} результатов из {total_count}")
    return message_responses


@router.get(
    "/users", 
    response_model=List[dict],
    summary="Поиск пользователей",
    description="""
    Выполняет поиск пользователей по имени или email.
    
    Используется для поиска пользователей при создании чата или добавлении участников.
    """
)
@async_time_it
async def search_users(
    query: str = Query(..., min_length=2, description="Текст для поиска"),
    limit: int = Query(10, ge=1, le=50, description="Ограничение количества результатов"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Поиск пользователей по имени или email
    """
    # Формируем запрос
    query_stmt = (
        select(User)
        .where(
            or_(
                User.name.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%")
            )
        )
        .where(User.id != current_user.id)  # Исключаем текущего пользователя
        .order_by(User.name)
        .limit(limit)
    )
    
    # Выполняем запрос
    result = await db.execute(query_stmt)
    users = result.scalars().all()
    
    # Преобразуем результаты в упрощенный формат
    user_responses = [
        {
            "id": str(user.id),
            "name": user.name,
            "email": user.email
        }
        for user in users
    ]
    
    logger.info(f"Поиск пользователей по запросу '{query}' вернул {len(user_responses)} результатов")
    return user_responses 