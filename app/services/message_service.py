from typing import List, Optional
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
        """
        Сохранение сообщения, отправленного через Centrifugo
        
        Args:
            user_id: ID пользователя, отправляющего сообщение
            message_in: Данные сообщения
            chat_id: ID чата
            
        Returns:
            Сохраненное сообщение
            
        Raises:
            HTTPException: Если чат не найден, пользователь не имеет доступа или произошла ошибка
        """
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
        chat_users = [str(user.id) for user in chat.users]
        if str(user_id) not in chat_users:
            logger.warning(f"Пользователь {user_id} не имеет доступа к чату {chat_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этому чату"
            )
        
        # Валидация данных сообщения
        self._validate_message_data(message_in)
        
        try:
            # Сохранение сообщения в БД
            message = await self.message_repo.create(
                chat_id=chat_id,
                sender_id=user_id,
                **message_in.dict()
            )
            
            # Публикация сообщения в Centrifugo
            await self._publish_message_to_centrifugo(chat_id, message)
            
            return message
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при сохранении сообщения: {str(e)}"
            )
    
    def _validate_message_data(self, message_in: MessageCreate) -> None:
        """
        Валидация данных сообщения
        
        Args:
            message_in: Данные сообщения
            
        Raises:
            HTTPException: Если данные не проходят валидацию
        """
        # Проверка длины текста
        if message_in.text and len(message_in.text) > 5000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Текст сообщения слишком длинный (максимум 5000 символов)"
            )
        
        # Проверка вложений
        if message_in.attachments:
            for attachment in message_in.attachments:
                if not attachment.type or not attachment.url:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Вложение должно содержать тип и URL"
                    )
                
                # Проверка URL вложения
                if not attachment.url.startswith(("http://", "https://", "ftp://", "s3://")):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Некорректный URL вложения: {attachment.url}"
                    )
    
    async def _publish_message_to_centrifugo(self, chat_id: UUID, message: MessageResponse) -> None:
        """
        Публикация сообщения в Centrifugo
        
        Args:
            chat_id: ID чата
            message: Сообщение для публикации
        """
        try:
            # Формирование канала чата
            chat_channel = f"chat:{chat_id}"
            
            # Публикация сообщения
            await centrifugo_client.publish(
                channel=chat_channel,
                data=message.dict()
            )
            logger.info(f"Сообщение {message.id} опубликовано в канал {chat_channel}")
        except Exception as e:
            logger.error(f"Ошибка при публикации сообщения в Centrifugo: {str(e)}", exc_info=True)
            # Не выбрасываем исключение, чтобы не блокировать сохранение сообщения
            # Клиент может получить сообщение при следующей синхронизации
    
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