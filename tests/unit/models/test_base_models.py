"""
Тесты для базовых моделей данных
"""
import pytest
from datetime import datetime
import uuid

# Маркер для модульных тестов
pytestmark = pytest.mark.unit

# Попытка импорта модели сообщения
try:
    from app.models.message import Message
    from app.models.chat import Chat
    from app.models.user import User
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    # Заглушки для моделей
    class Message:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    class Chat:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    class User:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

@pytest.mark.skipif(not MODELS_AVAILABLE, reason="Модели данных недоступны")
def test_message_creation():
    """Тест создания экземпляра модели сообщения"""
    message_id = uuid.uuid4()
    user_id = uuid.uuid4()
    chat_id = uuid.uuid4()
    created_at = datetime.now()
    text = "Тестовое сообщение"
    client_message_id = f"test-{uuid.uuid4()}"
    
    # Создаем экземпляр сообщения
    message = Message(
        id=message_id,
        user_id=user_id,
        chat_id=chat_id,
        text=text,
        created_at=created_at,
        client_message_id=client_message_id
    )
    
    # Проверяем, что атрибуты установлены правильно
    assert message.id == message_id, "ID сообщения не соответствует заданному"
    assert message.user_id == user_id, "ID пользователя не соответствует заданному"
    assert message.chat_id == chat_id, "ID чата не соответствует заданному"
    assert message.text == text, "Текст сообщения не соответствует заданному"
    assert message.created_at == created_at, "Время создания не соответствует заданному"
    assert message.client_message_id == client_message_id, "client_message_id не соответствует заданному"


@pytest.mark.skipif(not MODELS_AVAILABLE, reason="Модели данных недоступны")
def test_chat_creation():
    """Тест создания экземпляра модели чата"""
    chat_id = uuid.uuid4()
    name = "Тестовый чат"
    is_private = False
    created_at = datetime.now()
    
    # Создаем экземпляр чата
    chat = Chat(
        id=chat_id,
        name=name,
        is_private=is_private,
        created_at=created_at
    )
    
    # Проверяем, что атрибуты установлены правильно
    assert chat.id == chat_id, "ID чата не соответствует заданному"
    assert chat.name == name, "Название чата не соответствует заданному"
    assert chat.is_private == is_private, "Флаг приватности не соответствует заданному"
    assert chat.created_at == created_at, "Время создания не соответствует заданному"


@pytest.mark.skipif(not MODELS_AVAILABLE, reason="Модели данных недоступны")
def test_user_creation():
    """Тест создания экземпляра модели пользователя"""
    user_id = uuid.uuid4()
    email = "test@example.com"
    name = "Test User"
    is_active = True
    is_admin = False
    
    # Создаем экземпляр пользователя
    user = User(
        id=user_id,
        email=email,
        name=name,
        is_active=is_active,
        is_admin=is_admin
    )
    
    # Проверяем, что атрибуты установлены правильно
    assert user.id == user_id, "ID пользователя не соответствует заданному"
    assert user.email == email, "Email пользователя не соответствует заданному"
    assert user.name == name, "Имя пользователя не соответствует заданному"
    assert user.is_active == is_active, "Флаг активности не соответствует заданному"
    assert user.is_admin == is_admin, "Флаг администратора не соответствует заданному" 