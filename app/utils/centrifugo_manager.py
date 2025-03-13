"""
Утилита для управления соединениями Centrifugo.
Этот файл заменяет старый websocket_manager.py и обеспечивает аналогичную функциональность,
но использует Centrifugo для коммуникации в реальном времени.
"""
from typing import Dict, Set
from uuid import UUID

from app.core.logging import get_logger
from app.core.centrifugo import centrifugo_client

# Получение логгера
logger = get_logger("centrifugo_manager")


class CentrifugoManager:
    """Менеджер Centrifugo соединений и каналов"""
    
    def __init__(self):
        # Отслеживание участников чатов: chat_id -> множество user_id
        self.chat_participants: Dict[UUID, Set[UUID]] = {}
    
    def join_chat(self, chat_id: UUID, user_id: UUID):
        """
        Добавление пользователя в чат
        
        Args:
            chat_id: ID чата
            user_id: ID пользователя
        """
        if chat_id not in self.chat_participants:
            self.chat_participants[chat_id] = set()
        
        self.chat_participants[chat_id].add(user_id)
        logger.info(f"Пользователь {user_id} присоединился к чату {chat_id}")
        
        # Отправляем уведомление о присоединении пользователя
        channel = centrifugo_client.get_chat_channel_name(str(chat_id))
        try:
            centrifugo_client.publish(channel, {
                "event": "user_joined",
                "user_id": str(user_id),
                "chat_id": str(chat_id),
                "timestamp": centrifugo_client.get_timestamp()
            })
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о присоединении пользователя: {str(e)}")
    
    def leave_chat(self, chat_id: UUID, user_id: UUID):
        """
        Удаление пользователя из чата
        
        Args:
            chat_id: ID чата
            user_id: ID пользователя
        """
        if chat_id in self.chat_participants and user_id in self.chat_participants[chat_id]:
            self.chat_participants[chat_id].remove(user_id)
            logger.info(f"Пользователь {user_id} покинул чат {chat_id}")
            
            # Если в чате больше нет участников, удаляем чат
            if not self.chat_participants[chat_id]:
                del self.chat_participants[chat_id]
                logger.info(f"Чат {chat_id} не имеет активных участников и удален из отслеживания")
            
            # Отправляем уведомление о выходе пользователя
            channel = centrifugo_client.get_chat_channel_name(str(chat_id))
            try:
                centrifugo_client.publish(channel, {
                    "event": "user_left",
                    "user_id": str(user_id),
                    "chat_id": str(chat_id),
                    "timestamp": centrifugo_client.get_timestamp()
                })
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления о выходе пользователя: {str(e)}")
    
    async def send_personal_message(self, message: dict, user_id: UUID):
        """
        Отправка личного сообщения пользователю через его персональный канал
        
        Args:
            message: содержимое сообщения
            user_id: ID пользователя
        """
        user_channel = centrifugo_client.get_user_channel_name(str(user_id))
        try:
            await centrifugo_client.publish(user_channel, message)
            logger.info(f"Отправлено личное сообщение пользователю {user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке личного сообщения пользователю {user_id}: {str(e)}")
            return False
    
    async def broadcast_to_chat(self, message: dict, chat_id: UUID, exclude_user_id: UUID = None):
        """
        Отправка сообщения всем участникам чата
        
        Args:
            message: содержимое сообщения
            chat_id: ID чата
            exclude_user_id: ID пользователя, которому не нужно отправлять сообщение (обычно отправитель)
        """
        # В Centrifugo не нужно отдельно отправлять сообщение каждому пользователю,
        # достаточно опубликовать его в канал чата
        channel = centrifugo_client.get_chat_channel_name(str(chat_id))
        
        # Если нужно исключить пользователя, добавляем это в сообщение
        if exclude_user_id:
            message["exclude_user_id"] = str(exclude_user_id)
        
        try:
            await centrifugo_client.publish(channel, message)
            logger.info(f"Отправлено сообщение в чат {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в чат {chat_id}: {str(e)}")
            return False
    
    def get_chat_participants(self, chat_id: UUID) -> Set[UUID]:
        """
        Получение списка участников чата
        
        Args:
            chat_id: ID чата
            
        Returns:
            Set[UUID]: множество ID пользователей в чате
        """
        return self.chat_participants.get(chat_id, set())
    
    def is_user_in_chat(self, chat_id: UUID, user_id: UUID) -> bool:
        """
        Проверка, является ли пользователь участником чата
        
        Args:
            chat_id: ID чата
            user_id: ID пользователя
            
        Returns:
            bool: True, если пользователь в чате
        """
        return chat_id in self.chat_participants and user_id in self.chat_participants[chat_id]
    
    async def notify_typing(self, chat_id: UUID, user_id: UUID, is_typing: bool):
        """
        Отправка уведомления о наборе текста
        
        Args:
            chat_id: ID чата
            user_id: ID пользователя
            is_typing: True, если пользователь печатает, False если перестал
        """
        channel = centrifugo_client.get_chat_channel_name(str(chat_id))
        try:
            await centrifugo_client.publish(channel, {
                "event": "typing",
                "user_id": str(user_id),
                "chat_id": str(chat_id),
                "is_typing": is_typing,
                "timestamp": centrifugo_client.get_timestamp()
            })
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о наборе текста: {str(e)}")
            return False


# Создаем глобальный экземпляр менеджера
centrifugo_manager = CentrifugoManager() 