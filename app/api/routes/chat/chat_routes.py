from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_current_user
from app.core.logging import get_logger
from app.db.models import User
from app.db.repositories import ChatRepository, MessageRepository
from app.schemas.chat import ChatCreate, ChatResponse
from app.schemas.message import MessageResponse, MessageList

# Создание маршрутизатора
router = APIRouter(prefix="/chats", tags=["chats"])

# Получение логгера
logger = get_logger("chat_routes")


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_data: ChatCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Создание нового чата.
    
    Может быть создан как личный чат (direct) с одним участником,
    так и групповой чат с несколькими участниками.
    """
    logger.info(f"Пользователь {current_user.id} создает новый чат")
    chat_repo = ChatRepository(db)
    
    # Обработка типа чата
    if chat_data.type == "direct":
        if len(chat_data.user_ids) != 1:
            logger.warning(f"Попытка создать личный чат с количеством пользователей != 1: {len(chat_data.user_ids)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Личный чат должен содержать ровно одного получателя"
            )
        
        recipient_id = chat_data.user_ids[0]
        logger.debug(f"Создание личного чата между {current_user.id} и {recipient_id}")
        
        # Проверка существования пользователя выполняется в репозитории
        chat = await chat_repo.create_direct_chat(current_user.id, recipient_id)
        
    else:  # Group chat
        if not chat_data.name:
            logger.warning("Попытка создать групповой чат без имени")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Групповой чат должен иметь имя"
            )
        
        # Добавляем создателя чата в список участников, если его там нет
        user_ids = set(chat_data.user_ids)
        user_ids.add(current_user.id)
        
        logger.debug(f"Создание группового чата '{chat_data.name}' с пользователями: {user_ids}")
        chat = await chat_repo.create_group_chat(
            name=chat_data.name, 
            creator_id=current_user.id,
            user_ids=list(user_ids)
        )
    
    return ChatResponse(
        id=chat.id,
        name=chat.name,
        type=chat.type.value,
        created_at=chat.created_at,
        users=[{"id": user.id, "name": user.name, "email": user.email} for user in chat.users]
    )


@router.get("", response_model=List[ChatResponse])
async def get_user_chats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получение списка чатов текущего пользователя"""
    logger.info(f"Получение списка чатов пользователя {current_user.id}")
    chat_repo = ChatRepository(db)
    chats = await chat_repo.get_user_chats(current_user.id)
    
    return [
        ChatResponse(
            id=chat.id,
            name=chat.name,
            type=chat.type.value,
            created_at=chat.created_at,
            users=[{"id": user.id, "name": user.name, "email": user.email} for user in chat.users]
        ) for chat in chats
    ]


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получение информации о конкретном чате"""
    logger.info(f"Получение информации о чате {chat_id} пользователем {current_user.id}")
    chat_repo = ChatRepository(db)
    chats = await chat_repo.get_user_chats(current_user.id)
    
    # Проверяем, что чат существует и пользователь имеет к нему доступ
    chat = next((c for c in chats if c.id == chat_id), None)
    if not chat:
        logger.warning(f"Пользователь {current_user.id} пытается получить доступ к несуществующему чату {chat_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден или у вас нет доступа к нему"
        )
    
    return ChatResponse(
        id=chat.id,
        name=chat.name,
        type=chat.type.value,
        created_at=chat.created_at,
        users=[{"id": user.id, "name": user.name, "email": user.email} for user in chat.users]
    )


@router.get("/{chat_id}/messages", response_model=MessageList)
async def get_chat_messages(
    chat_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получение сообщений из чата с пагинацией"""
    logger.info(f"Получение сообщений чата {chat_id} пользователем {current_user.id}")
    chat_repo = ChatRepository(db)
    message_repo = MessageRepository(db)
    
    # Проверяем, что пользователь имеет доступ к чату
    chats = await chat_repo.get_user_chats(current_user.id)
    if not any(c.id == chat_id for c in chats):
        logger.warning(f"Пользователь {current_user.id} пытается получить доступ к сообщениям чата {chat_id}, к которому не имеет доступа")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден или у вас нет доступа к нему"
        )
    
    # Получаем сообщения
    messages = await message_repo.get_chat_messages(chat_id, limit, offset)
    
    # Преобразуем в ответ
    message_responses = [
        MessageResponse(
            id=msg.id,
            chat_id=msg.chat_id,
            sender_id=msg.sender_id,
            text=msg.text,
            created_at=msg.created_at,
            updated_at=msg.updated_at,
            is_read=msg.is_read,
            client_message_id=msg.client_message_id
        ) for msg in messages
    ]
    
    return MessageList(messages=message_responses, count=len(message_responses)) 