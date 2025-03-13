# Импорт всех моделей для удобного доступа
from app.db.models.chat import Chat, ChatType, user_chat
from app.db.models.message import Message
from app.db.models.user import User

# Экспорт моделей для использования из других модулей
__all__ = [
    "User",
    "Chat",
    "ChatType",
    "Message",
    "user_chat"
] 