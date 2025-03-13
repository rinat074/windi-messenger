from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.repositories.chat import ChatRepository
from app.db.repositories.message import MessageRepository
from app.schemas.message import MessageCreate, MessageResponse
from app.core.centrifugo import centrifugo_client

# Получение логгера для этого модуля
logger = get_logger("message_service")

class MessageService:
    """Сервис для работы с сообщениями"""
    
    def __init__(self, db: AsyncSession):
        self.message_repo = MessageRepository(db)
        self.chat_repo = ChatRepository(db)
    
    async def save_message(self, user_id: UUID, message_in: MessageCreate, chat_id: UUID) -> MessageResponse:
        """Сохранение сообщения, отправленного через Centrifugo"""
        logger.info(f"Сохранение сообщения от пользователя {user_id} в чат {chat_id}")
        
        # Проверка наличия чата и доступа пользователя к нему
        chat = await self.chat_repo.get_by_id(chat_id)
        if not chat:
            logger.warning(f"Попытка отправить сообщение в несуществующий чат {chat_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Чат не найден"
            )
        
        # Проверка, является ли пользователь участником чата
        chat_users = [user.id for user in chat.users]
        if user_id not in chat_users:
            logger.warning(f"Пользователь {user_id} пытается отправить сообщение в чат {chat.id} без доступа")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этому чату"
            )
        
        # Сохранение сообщения с проверкой на дубликаты
        if message_in.client_message_id:
            logger.debug(f"Проверка на дубликат сообщения с client_message_id={message_in.client_message_id}")
        
        message = await self.message_repo.save_message(
            chat_id=chat_id,
            sender_id=user_id,
            text=message_in.text,
            client_message_id=message_in.client_message_id
        )
        
        # Проверяем, был ли это дубликат, сравнивая поля created_at и updated_at
        # Если это дубликат, то created_at должно быть раньше, чем updated_at
        is_duplicate = message_in.client_message_id and message.created_at != message.updated_at
        
        if is_duplicate:
            logger.info(f"Обнаружен дубликат сообщения с client_message_id={message_in.client_message_id}")
        else:
            logger.info(f"Сообщение успешно сохранено: id={message.id}")
            
            # Публикуем сообщение в Centrifugo
            try:
                channel = centrifugo_client.get_chat_channel_name(str(chat_id))
                centrifugo_message = {
                    "id": str(message.id),
                    "chat_id": str(message.chat_id),
                    "sender_id": str(message.sender_id),
                    "text": message.text,
                    "created_at": message.created_at.isoformat(),
                    "is_read": message.is_read,
                    "client_message_id": message.client_message_id
                }
                await centrifugo_client.publish(channel, centrifugo_message)
                logger.info(f"Сообщение опубликовано в канал Centrifugo: {channel}")
            except Exception as e:
                logger.error(f"Ошибка при публикации сообщения в Centrifugo: {str(e)}")
        
        return MessageResponse(
            id=message.id,
            chat_id=message.chat_id,
            sender_id=message.sender_id,
            text=message.text,
            created_at=message.created_at,
            updated_at=message.updated_at,
            is_read=message.is_read,
            client_message_id=message.client_message_id
        )
    
    async def get_chat_history(self, user_id: UUID, chat_id: UUID, limit: int = 50, offset: int = 0) -> List[MessageResponse]:
        """Получение истории сообщений чата с пагинацией"""
        logger.info(f"Запрос истории сообщений чата {chat_id} пользователем {user_id} (limit={limit}, offset={offset})")
        
        # Проверка наличия чата и доступа пользователя к нему
        chat = await self.chat_repo.get_by_id(chat_id)
        if not chat:
            logger.warning(f"Попытка получить историю несуществующего чата {chat_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Чат не найден"
            )
        
        # Проверка, является ли пользователь участником чата
        chat_users = [user.id for user in chat.users]
        if user_id not in chat_users:
            logger.warning(f"Пользователь {user_id} пытается получить историю чата {chat.id} без доступа")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этому чату"
            )
        
        # Получение сообщений с пагинацией
        messages = await self.message_repo.get_chat_messages(chat_id, limit, offset)
        logger.info(f"Получено {len(messages)} сообщений для чата {chat_id}")
        
        return [MessageResponse(
            id=msg.id,
            chat_id=msg.chat_id,
            sender_id=msg.sender_id,
            text=msg.text,
            created_at=msg.created_at,
            updated_at=msg.updated_at,
            is_read=msg.is_read,
            client_message_id=msg.client_message_id
        ) for msg in messages]
    
    async def mark_message_as_read(self, user_id: UUID, message_id: UUID) -> MessageResponse:
        """Отметка сообщения как прочитанного"""
        logger.info(f"Отметка сообщения {message_id} как прочитанного пользователем {user_id}")
        
        # Получение сообщения
        message = await self.message_repo.get_by_id(message_id)
        if not message:
            logger.warning(f"Попытка отметить несуществующее сообщение {message_id} как прочитанное")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Сообщение не найдено"
            )
        
        # Проверка, является ли пользователь участником чата
        chat = await self.chat_repo.get_by_id(message.chat_id)
        chat_users = [user.id for user in chat.users]
        if user_id not in chat_users:
            logger.warning(f"Пользователь {user_id} пытается отметить сообщение в чате {chat.id} без доступа")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этому сообщению"
            )
        
        # Отметка сообщения как прочитанного
        updated_message = await self.message_repo.mark_as_read(message_id)
        logger.info(f"Сообщение {message_id} успешно отмечено как прочитанное")
        
        # Отправляем уведомление о прочтении через Centrifugo
        try:
            channel = centrifugo_client.get_chat_channel_name(str(message.chat_id))
            centrifugo_client.publish(channel, {
                "event": "message_read",
                "message_id": str(message_id),
                "user_id": str(user_id),
                "chat_id": str(message.chat_id),
                "timestamp": updated_message.updated_at.isoformat()
            })
            logger.info(f"Уведомление о прочтении опубликовано в канал Centrifugo: {channel}")
        except Exception as e:
            logger.error(f"Ошибка при публикации уведомления о прочтении в Centrifugo: {str(e)}")
        
        return MessageResponse(
            id=updated_message.id,
            chat_id=updated_message.chat_id,
            sender_id=updated_message.sender_id,
            text=updated_message.text,
            created_at=updated_message.created_at,
            updated_at=updated_message.updated_at,
            is_read=updated_message.is_read,
            client_message_id=updated_message.client_message_id
        ) 