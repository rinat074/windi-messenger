from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.core.logging import get_logger
from app.db.models.chat import Chat, ChatType, user_chat
from app.db.repositories.base import BaseRepository

# Получение логгера
logger = get_logger("chat_repository")


class ChatRepository(BaseRepository):
    """Репозиторий для работы с чатами"""
    
    def __init__(self, db: AsyncSession):
        """
        Инициализация репозитория чатов
        
        Args:
            db: Сессия базы данных
        """
        super().__init__(db, Chat)
    
    async def create_direct_chat(self, user1_id: UUID, user2_id: UUID) -> Chat:
        """
        Создание личного чата между двумя пользователями
        
        Args:
            user1_id: ID первого пользователя
            user2_id: ID второго пользователя
            
        Returns:
            Объект созданного или существующего чата
        """
        # Проверяем существование чата между пользователями
        stmt = select(Chat).join(user_chat, Chat.id == user_chat.c.chat_id).where(
            Chat.type == ChatType.DIRECT,
            user_chat.c.user_id.in_([user1_id, user2_id])
        ).group_by(Chat.id).having(func.count(user_chat.c.user_id) == 2)
        
        result = await self.db.execute(stmt)
        existing_chat = result.scalar_one_or_none()
        
        if existing_chat:
            logger.info(f"Найден существующий личный чат между пользователями {user1_id} и {user2_id}")
            return existing_chat
        
        # Создаем новый чат
        logger.info(f"Создание нового личного чата между пользователями {user1_id} и {user2_id}")
        chat = Chat(type=ChatType.DIRECT)
        self.db.add(chat)
        await self.db.flush()
        
        # Добавляем пользователей в чат
        await self.add_user_to_chat(chat.id, user1_id)
        await self.add_user_to_chat(chat.id, user2_id)
        
        await self.db.commit()
        await self.db.refresh(chat)
        return chat
    
    async def create_group_chat(self, name: str, creator_id: UUID, user_ids: List[UUID]) -> Chat:
        """
        Создание группового чата
        
        Args:
            name: Название группового чата
            creator_id: ID пользователя-создателя
            user_ids: Список ID пользователей-участников
            
        Returns:
            Объект созданного группового чата
        """
        logger.info(f"Создание группового чата '{name}' пользователем {creator_id} с {len(user_ids)} участниками")
        chat = Chat(name=name, type=ChatType.GROUP)
        self.db.add(chat)
        await self.db.flush()
        
        # Добавляем создателя и участников в чат
        await self.add_user_to_chat(chat.id, creator_id)
        for user_id in user_ids:
            if user_id != creator_id:  # Избегаем дублирования
                await self.add_user_to_chat(chat.id, user_id)
        
        await self.db.commit()
        await self.db.refresh(chat)
        return chat
    
    async def add_user_to_chat(self, chat_id: UUID, user_id: UUID) -> None:
        """
        Добавление пользователя в чат
        
        Args:
            chat_id: ID чата
            user_id: ID пользователя
        """
        logger.debug(f"Добавление пользователя {user_id} в чат {chat_id}")
        stmt = user_chat.insert().values(chat_id=chat_id, user_id=user_id)
        await self.db.execute(stmt)
    
    async def get_user_chats(self, user_id: UUID) -> List[Chat]:
        """
        Получение всех чатов пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список чатов, в которых участвует пользователь
        """
        logger.debug(f"Получение списка чатов пользователя {user_id}")
        stmt = select(Chat).join(user_chat).where(user_chat.c.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().all() 