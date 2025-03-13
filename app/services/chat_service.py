from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.chat import Chat, ChatType
from app.db.repositories.chat import ChatRepository
from app.db.repositories.user import UserRepository
from app.schemas.chat import DirectChatCreate, GroupChatCreate, UserChatResponse

# Получение логгера
logger = get_logger("chat_service")


class ChatService:
    """Сервис для работы с чатами"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.chat_repo = ChatRepository(db)
        self.user_repo = UserRepository(db)
    
    async def create_direct_chat(self, user_id: UUID, chat_data: DirectChatCreate) -> Chat:
        """Создание личного чата между двумя пользователями"""
        logger.info(f"Создание личного чата: пользователь {user_id} с пользователем {chat_data.user_id}")
        
        # Проверка существования получателя
        recipient = await self.user_repo.get_by_id(chat_data.user_id)
        if not recipient:
            logger.warning(f"Попытка создать чат с несуществующим пользователем: {chat_data.user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь-получатель не найден"
            )
        
        # Проверка на создание чата с самим собой
        if user_id == chat_data.user_id:
            logger.warning(f"Пользователь {user_id} пытается создать чат с самим собой")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя создать чат с самим собой"
            )
        
        # Создание личного чата
        chat = await self.chat_repo.create_direct_chat(user_id, chat_data.user_id)
        logger.info(f"Создан личный чат {chat.id} между пользователями {user_id} и {chat_data.user_id}")
        
        return chat
    
    async def create_group_chat(self, user_id: UUID, chat_data: GroupChatCreate) -> Chat:
        """Создание группового чата"""
        logger.info(f"Создание группового чата '{chat_data.name}' пользователем {user_id}")
        
        # Проверка существования всех пользователей
        for member_id in chat_data.user_ids:
            member = await self.user_repo.get_by_id(member_id)
            if not member:
                logger.warning(f"Попытка добавить несуществующего пользователя {member_id} в групповой чат")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Пользователь с ID {member_id} не найден"
                )
        
        # Создание группового чата
        chat = await self.chat_repo.create_group_chat(
            name=chat_data.name,
            creator_id=user_id,
            user_ids=chat_data.user_ids
        )
        
        logger.info(f"Создан групповой чат {chat.id} с названием '{chat_data.name}'")
        return chat
    
    async def get_chat_by_id(self, chat_id: UUID, user_id: UUID) -> Chat:
        """Получение чата по ID с проверкой доступа"""
        logger.info(f"Получение чата {chat_id} пользователем {user_id}")
        
        # Получение чата
        chat = await self.chat_repo.get_by_id(chat_id)
        if not chat:
            logger.warning(f"Попытка получить несуществующий чат {chat_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Чат не найден"
            )
        
        # Проверка, является ли пользователь участником чата
        chat_users = [user.id for user in chat.users]
        if user_id not in chat_users:
            logger.warning(f"Пользователь {user_id} пытается получить доступ к чату {chat_id} без прав")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этому чату"
            )
        
        return chat
    
    async def get_user_chats(self, user_id: UUID) -> List[UserChatResponse]:
        """Получение всех чатов пользователя"""
        logger.info(f"Получение списка чатов пользователя {user_id}")
        
        # Получение чатов пользователя
        chats = await self.chat_repo.get_user_chats(user_id)
        
        # Преобразование в формат ответа
        result = []
        for chat in chats:
            # Получение другого пользователя для личных чатов
            other_user = None
            if chat.type == ChatType.DIRECT:
                for user in chat.users:
                    if user.id != user_id:
                        other_user = user
                        break
            
            # Формирование названия для личных чатов
            name = chat.name
            if chat.type == ChatType.DIRECT and other_user:
                name = other_user.name
            
            result.append(UserChatResponse(
                id=chat.id,
                name=name,
                type=chat.type,
                users=[{
                    "id": user.id,
                    "name": user.name,
                    "email": user.email
                } for user in chat.users]
            ))
        
        return result
    
    async def add_user_to_chat(self, chat_id: UUID, user_id: UUID, current_user_id: UUID) -> Chat:
        """Добавление пользователя в чат"""
        logger.info(f"Добавление пользователя {user_id} в чат {chat_id} пользователем {current_user_id}")
        
        # Получение чата с проверкой доступа
        chat = await self.get_chat_by_id(chat_id, current_user_id)
        
        # Проверка существования пользователя
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning(f"Попытка добавить несуществующего пользователя {user_id} в чат {chat_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )
        
        # Проверка, что это групповой чат
        if chat.type != ChatType.GROUP:
            logger.warning(f"Попытка добавить пользователя {user_id} в личный чат {chat_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя добавить пользователя в личный чат"
            )
        
        # Проверка, что пользователь еще не в чате
        chat_users = [user.id for user in chat.users]
        if user_id in chat_users:
            logger.warning(f"Пользователь {user_id} уже состоит в чате {chat_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь уже состоит в этом чате"
            )
        
        # Добавление пользователя в чат
        await self.chat_repo.add_user_to_chat(chat_id, user_id)
        
        # Обновление данных чата
        await self.db.refresh(chat)
        logger.info(f"Пользователь {user_id} добавлен в чат {chat_id}")
        
        return chat 