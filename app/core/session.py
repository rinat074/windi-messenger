"""
Модуль для управления пользовательскими сессиями на разных устройствах.
Позволяет отслеживать активные сессии, авторизовывать и деавторизовывать устройства.
"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.core.logging import get_logger
from app.core.centrifugo import centrifugo_client

# Получение логгера
logger = get_logger("session_manager")


class DeviceInfo(BaseModel):
    """Информация об устройстве, с которого выполнен вход"""
    device_id: str
    device_name: str
    ip_address: str
    user_agent: str
    last_active: datetime
    created_at: datetime


class SessionInfo(BaseModel):
    """Информация о сессии пользователя"""
    session_id: str
    user_id: str
    device_info: DeviceInfo
    is_active: bool = True


class SessionManager:
    """
    Менеджер сессий для управления подключениями пользователей с разных устройств
    """
    
    # Singleton instance
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Инициализация менеджера сессий"""
        if self._initialized:
            return
        
        # Словарь всех сессий: user_id -> {session_id -> SessionInfo}
        self.sessions: Dict[str, Dict[str, SessionInfo]] = {}
        
        # Словарь соответствия session_id -> user_id
        self.session_to_user: Dict[str, str] = {}
        
        # Инициализировано
        self._initialized = True
        logger.info("Инициализирован SessionManager")
    
    def create_session(
        self, 
        user_id: str, 
        device_name: str, 
        ip_address: str, 
        user_agent: str
    ) -> str:
        """
        Создание новой сессии для пользователя
        
        Args:
            user_id: ID пользователя
            device_name: Название устройства
            ip_address: IP-адрес
            user_agent: User-Agent браузера/клиента
            
        Returns:
            str: ID созданной сессии
        """
        # Генерируем уникальный ID сессии
        session_id = str(uuid.uuid4())
        
        # Генерируем уникальный ID устройства
        device_id = str(uuid.uuid4())
        
        # Создаем информацию об устройстве
        device_info = DeviceInfo(
            device_id=device_id,
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent,
            last_active=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        
        # Создаем информацию о сессии
        session_info = SessionInfo(
            session_id=session_id,
            user_id=user_id,
            device_info=device_info
        )
        
        # Сохраняем сессию
        if user_id not in self.sessions:
            self.sessions[user_id] = {}
        self.sessions[user_id][session_id] = session_info
        self.session_to_user[session_id] = user_id
        
        logger.info(f"Создана новая сессия {session_id} для пользователя {user_id} на устройстве {device_name}")
        return session_id
    
    def update_session_activity(self, session_id: str) -> bool:
        """
        Обновление времени последней активности сессии
        
        Args:
            session_id: ID сессии
            
        Returns:
            bool: True, если сессия успешно обновлена
        """
        if session_id not in self.session_to_user:
            logger.warning(f"Попытка обновить несуществующую сессию: {session_id}")
            return False
        
        user_id = self.session_to_user[session_id]
        
        # Обновляем время последней активности
        self.sessions[user_id][session_id].device_info.last_active = datetime.utcnow()
        logger.debug(f"Обновлено время активности сессии {session_id}")
        return True
    
    def terminate_session(self, session_id: str) -> bool:
        """
        Принудительное завершение сессии
        
        Args:
            session_id: ID сессии для завершения
            
        Returns:
            bool: True, если сессия успешно завершена
        """
        if session_id not in self.session_to_user:
            logger.warning(f"Попытка завершить несуществующую сессию: {session_id}")
            return False
        
        user_id = self.session_to_user[session_id]
        
        # Отправляем уведомление через Centrifugo о завершении сессии
        user_channel = centrifugo_client.get_user_channel_name(user_id)
        try:
            centrifugo_client.publish(user_channel, {
                "event": "session_terminated",
                "data": {
                    "session_id": session_id,
                    "message": "Сессия завершена с другого устройства"
                }
            })
            logger.info(f"Отправлено уведомление о завершении сессии {session_id} через Centrifugo")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о завершении сессии через Centrifugo: {str(e)}")
        
        # Помечаем сессию как неактивную
        self.sessions[user_id][session_id].is_active = False
        
        logger.info(f"Сессия {session_id} пользователя {user_id} принудительно завершена")
        return True
    
    def validate_session(self, session_id: str) -> bool:
        """
        Проверка валидности сессии
        
        Args:
            session_id: ID сессии для проверки
            
        Returns:
            bool: True, если сессия существует и активна
        """
        if session_id not in self.session_to_user:
            return False
        
        user_id = self.session_to_user[session_id]
        
        if user_id not in self.sessions or session_id not in self.sessions[user_id]:
            return False
        
        return self.sessions[user_id][session_id].is_active
    
    def get_user_sessions(self, user_id: str) -> List[SessionInfo]:
        """
        Получение списка всех сессий пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            List[SessionInfo]: Список информации о сессиях
        """
        if user_id not in self.sessions:
            return []
        
        # Возвращаем копию информации о сессиях
        return list(self.sessions[user_id].values())
    
    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """
        Получение информации о сессии
        
        Args:
            session_id: ID сессии
            
        Returns:
            Optional[SessionInfo]: Информация о сессии или None, если сессия не найдена
        """
        if session_id not in self.session_to_user:
            return None
        
        user_id = self.session_to_user[session_id]
        
        if user_id not in self.sessions or session_id not in self.sessions[user_id]:
            return None
        
        return self.sessions[user_id][session_id]
    
    def clean_inactive_sessions(self, max_age_days: int = 30) -> int:
        """
        Очистка неактивных сессий
        
        Args:
            max_age_days: Максимальный возраст неактивных сессий в днях
            
        Returns:
            int: Количество удаленных сессий
        """
        threshold = datetime.utcnow() - timedelta(days=max_age_days)
        removed_count = 0
        
        # Создаем копию, чтобы избежать изменения словаря во время итерации
        users_to_check = list(self.sessions.keys())
        
        for user_id in users_to_check:
            sessions_to_remove = []
            
            for session_id, session_info in self.sessions[user_id].items():
                if (not session_info.is_active and 
                    session_info.device_info.last_active < threshold):
                    sessions_to_remove.append(session_id)
            
            # Удаляем устаревшие сессии
            for session_id in sessions_to_remove:
                del self.sessions[user_id][session_id]
                if session_id in self.session_to_user:
                    del self.session_to_user[session_id]
                removed_count += 1
            
            # Если у пользователя не осталось сессий, удаляем его из словаря
            if not self.sessions[user_id]:
                del self.sessions[user_id]
        
        logger.info(f"Очистка сессий: удалено {removed_count} неактивных сессий")
        return removed_count
    
    def broadcast_to_user(self, user_id: str, message: Dict) -> bool:
        """
        Отправка сообщения всем активным соединениям пользователя через Centrifugo
        
        Args:
            user_id: ID пользователя
            message: Сообщение для отправки
            
        Returns:
            bool: True, если сообщение успешно отправлено
        """
        if user_id not in self.sessions:
            logger.warning(f"Попытка отправить сообщение несуществующему пользователю: {user_id}")
            return False
        
        try:
            # Отправляем сообщение через Centrifugo в персональный канал пользователя
            user_channel = centrifugo_client.get_user_channel_name(user_id)
            centrifugo_client.publish(user_channel, message)
            
            logger.info(f"Отправлено сообщение пользователю {user_id} через Centrifugo")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения через Centrifugo: {str(e)}")
            return False
    
    def get_active_sessions_count(self) -> int:
        """
        Получение количества активных сессий
        
        Returns:
            int: Количество активных сессий
        """
        count = 0
        for user_id in self.sessions:
            for session_id in self.sessions[user_id]:
                if self.sessions[user_id][session_id].is_active:
                    count += 1
        return count


# Создание глобального экземпляра менеджера сессий
session_manager = SessionManager() 