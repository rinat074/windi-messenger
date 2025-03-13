"""
УСТАРЕВШИЙ ФАЙЛ: Этот файл оставлен для обратной совместимости.
Пожалуйста, используйте app.utils.centrifugo_manager вместо этого модуля.
"""
import warnings

warnings.warn(
    "Модуль app.utils.websocket_manager устарел и будет удален в следующих версиях. "
    "Используйте app.utils.centrifugo_manager вместо него.", 
    DeprecationWarning, 
    stacklevel=2
)

# Перенаправляем импорты на новый модуль
from app.utils.centrifugo_manager import centrifugo_manager

# Для обратной совместимости создаем старый класс и экземпляр
class ConnectionManager:
    """
    УСТАРЕВШИЙ КЛАСС: Этот класс оставлен для обратной совместимости.
    Пожалуйста, используйте CentrifugoManager из модуля app.utils.centrifugo_manager.
    """
    def __init__(self):
        warnings.warn(
            "Класс ConnectionManager устарел. Используйте CentrifugoManager вместо него.",
            DeprecationWarning, 
            stacklevel=2
        )
        self._centrifugo_manager = centrifugo_manager
    
    # Методы-прокси для обратной совместимости
    async def connect(self, *args, **kwargs):
        warnings.warn("Метод connect() устарел и больше не используется с Centrifugo", DeprecationWarning)
        return True
    
    def disconnect(self, *args, **kwargs):
        warnings.warn("Метод disconnect() устарел и больше не используется с Centrifugo", DeprecationWarning)
        return True
    
    def join_chat(self, chat_id, user_id):
        return self._centrifugo_manager.join_chat(chat_id, user_id)
    
    def leave_chat(self, chat_id, user_id):
        return self._centrifugo_manager.leave_chat(chat_id, user_id)
    
    async def send_personal_message(self, message, user_id):
        return await self._centrifugo_manager.send_personal_message(message, user_id)
    
    async def broadcast_to_chat(self, message, chat_id, exclude_user_id=None):
        return await self._centrifugo_manager.broadcast_to_chat(message, chat_id, exclude_user_id)


# Для обратной совместимости
manager = ConnectionManager() 