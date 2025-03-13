from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.message import Message
from app.db.repositories.base import BaseRepository

# Получение логгера
logger = get_logger("message_repository")


class MessageRepository(BaseRepository):
    """Репозиторий для работы с сообщениями"""
    
    def __init__(self, db: AsyncSession):
        """
        Инициализация репозитория сообщений
        
        Args:
            db: Сессия базы данных
        """
        super().__init__(db, Message)
    
    async def get_chat_messages(self, chat_id: UUID, limit: int = 50, offset: int = 0) -> List[Message]:
        """
        Получение сообщений чата с пагинацией
        
        Args:
            chat_id: ID чата
            limit: Максимальное количество сообщений (по умолчанию 50)
            offset: Смещение для пагинации (по умолчанию 0)
            
        Returns:
            Список сообщений чата
        """
        logger.debug(f"Получение сообщений чата {chat_id} с limit={limit}, offset={offset}")
        stmt = select(Message).filter(
            Message.chat_id == chat_id
        ).order_by(
            Message.created_at.asc()
        ).limit(limit).offset(offset)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def save_message(self, chat_id: UUID, sender_id: UUID, text: str, client_message_id: str = None) -> Message:
        """
        Сохранение сообщения с проверкой на дубликат
        
        Args:
            chat_id: ID чата
            sender_id: ID отправителя
            text: Текст сообщения
            client_message_id: Клиентский ID для предотвращения дубликатов
            
        Returns:
            Объект сохраненного сообщения
        """
        if client_message_id:
            # Проверка на дубликат
            logger.debug(f"Проверка на дубликат сообщения с client_message_id={client_message_id}")
            stmt = select(Message).filter(
                Message.client_message_id == client_message_id,
                Message.chat_id == chat_id,
                Message.sender_id == sender_id
            )
            result = await self.db.execute(stmt)
            duplicate = result.scalar_one_or_none()
            
            if duplicate:
                logger.info(f"Обнаружен дубликат сообщения с client_message_id={client_message_id}")
                return duplicate
        
        # Создание нового сообщения
        logger.debug(f"Создание нового сообщения от пользователя {sender_id} в чате {chat_id}")
        message = Message(
            chat_id=chat_id,
            sender_id=sender_id,
            text=text,
            client_message_id=client_message_id
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message
    
    async def mark_as_read(self, message_id: UUID) -> Message:
        """
        Отметка сообщения как прочитанного
        
        Args:
            message_id: ID сообщения
            
        Returns:
            Обновленный объект сообщения
        """
        logger.debug(f"Отметка сообщения {message_id} как прочитанного")
        message = await self.get_by_id(message_id)
        if message:
            message.is_read = True
            await self.db.commit()
            await self.db.refresh(message)
        return message 