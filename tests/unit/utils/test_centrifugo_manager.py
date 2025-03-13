"""
Модульные тесты для CentrifugoManager
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
import uuid

from app.utils.centrifugo_manager import CentrifugoManager


@pytest.fixture
def mock_centrifugo_client(monkeypatch):
    """Фикстура, предоставляющая мок для centrifugo_client"""
    mock_client = AsyncMock()
    
    # Настраиваем методы мока
    mock_client.publish = AsyncMock(return_value={"success": True})
    mock_client.get_chat_channel_name = MagicMock(side_effect=lambda chat_id: f"chat:{chat_id}")
    mock_client.get_user_channel_name = MagicMock(side_effect=lambda user_id: f"user:{user_id}")
    mock_client.get_timestamp = MagicMock(return_value="2023-01-01T00:00:00Z")
    
    # Подменяем реальный клиент моком
    monkeypatch.setattr("app.utils.centrifugo_manager.centrifugo_client", mock_client)
    
    return mock_client


@pytest.fixture
def test_manager():
    """Создает чистый экземпляр CentrifugoManager для тестов"""
    return CentrifugoManager()


def test_join_chat(test_manager, mock_centrifugo_client):
    """Тест добавления пользователя в чат"""
    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    # Вызываем тестируемый метод
    test_manager.join_chat(chat_id, user_id)
    
    # Проверяем, что пользователь добавлен в список участников чата
    assert chat_id in test_manager.chat_participants
    assert user_id in test_manager.chat_participants[chat_id]
    
    # Проверяем, что вызван метод публикации уведомления
    channel_name = mock_centrifugo_client.get_chat_channel_name(str(chat_id))
    mock_centrifugo_client.publish.assert_called_once()
    # Проверяем аргументы вызова
    args, kwargs = mock_centrifugo_client.publish.call_args
    assert args[0] == channel_name
    assert args[1]["event"] == "user_joined"
    assert args[1]["user_id"] == str(user_id)
    assert args[1]["chat_id"] == str(chat_id)


def test_leave_chat(test_manager, mock_centrifugo_client):
    """Тест удаления пользователя из чата"""
    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    # Добавляем пользователя в чат
    test_manager.chat_participants[chat_id] = {user_id}
    
    # Вызываем тестируемый метод
    test_manager.leave_chat(chat_id, user_id)
    
    # Проверяем, что пользователь удален из списка участников чата
    assert chat_id not in test_manager.chat_participants  # Чат должен быть удален, т.к. в нем не осталось участников
    
    # Проверяем, что вызван метод публикации уведомления
    channel_name = mock_centrifugo_client.get_chat_channel_name(str(chat_id))
    mock_centrifugo_client.publish.assert_called_once()
    # Проверяем аргументы вызова
    args, kwargs = mock_centrifugo_client.publish.call_args
    assert args[0] == channel_name
    assert args[1]["event"] == "user_left"
    assert args[1]["user_id"] == str(user_id)
    assert args[1]["chat_id"] == str(chat_id)


def test_leave_chat_multiple_users(test_manager, mock_centrifugo_client):
    """Тест удаления пользователя из чата с несколькими участниками"""
    chat_id = uuid.uuid4()
    user_id1 = uuid.uuid4()
    user_id2 = uuid.uuid4()
    
    # Добавляем нескольких пользователей в чат
    test_manager.chat_participants[chat_id] = {user_id1, user_id2}
    
    # Вызываем тестируемый метод для одного пользователя
    test_manager.leave_chat(chat_id, user_id1)
    
    # Проверяем, что только указанный пользователь удален
    assert chat_id in test_manager.chat_participants
    assert user_id1 not in test_manager.chat_participants[chat_id]
    assert user_id2 in test_manager.chat_participants[chat_id]


@pytest.mark.asyncio
async def test_send_personal_message(test_manager, mock_centrifugo_client):
    """Тест отправки личного сообщения пользователю"""
    user_id = uuid.uuid4()
    message = {"event": "test_event", "data": "test_data"}
    
    # Вызываем тестируемый метод
    result = await test_manager.send_personal_message(message, user_id)
    
    # Проверяем результат
    assert result == True
    
    # Проверяем, что вызван метод публикации в правильный канал
    user_channel = mock_centrifugo_client.get_user_channel_name(str(user_id))
    mock_centrifugo_client.publish.assert_called_once_with(user_channel, message)


@pytest.mark.asyncio
async def test_broadcast_to_chat(test_manager, mock_centrifugo_client):
    """Тест отправки сообщения всем участникам чата"""
    chat_id = uuid.uuid4()
    message = {"event": "test_event", "data": "test_data"}
    
    # Вызываем тестируемый метод
    result = await test_manager.broadcast_to_chat(message, chat_id)
    
    # Проверяем результат
    assert result == True
    
    # Проверяем, что вызван метод публикации в правильный канал
    chat_channel = mock_centrifugo_client.get_chat_channel_name(str(chat_id))
    mock_centrifugo_client.publish.assert_called_once_with(chat_channel, message)


@pytest.mark.asyncio
async def test_broadcast_to_chat_with_exclusion(test_manager, mock_centrifugo_client):
    """Тест отправки сообщения всем участникам чата с исключением отправителя"""
    chat_id = uuid.uuid4()
    exclude_user_id = uuid.uuid4()
    message = {"event": "test_event", "data": "test_data"}
    
    # Вызываем тестируемый метод
    result = await test_manager.broadcast_to_chat(message, chat_id, exclude_user_id)
    
    # Проверяем результат
    assert result == True
    
    # Проверяем, что вызван метод публикации с правильными параметрами
    chat_channel = mock_centrifugo_client.get_chat_channel_name(str(chat_id))
    mock_centrifugo_client.publish.assert_called_once()
    
    # Проверяем аргументы вызова
    args, kwargs = mock_centrifugo_client.publish.call_args
    assert args[0] == chat_channel
    assert args[1]["event"] == "test_event"
    assert args[1]["data"] == "test_data"
    assert args[1]["exclude_user_id"] == str(exclude_user_id)


@pytest.mark.asyncio
async def test_notify_typing(test_manager, mock_centrifugo_client):
    """Тест отправки уведомления о наборе текста"""
    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    is_typing = True
    
    # Вызываем тестируемый метод
    result = await test_manager.notify_typing(chat_id, user_id, is_typing)
    
    # Проверяем результат
    assert result == True
    
    # Проверяем, что вызван метод публикации с правильными параметрами
    chat_channel = mock_centrifugo_client.get_chat_channel_name(str(chat_id))
    mock_centrifugo_client.publish.assert_called_once()
    
    # Проверяем аргументы вызова
    args, kwargs = mock_centrifugo_client.publish.call_args
    assert args[0] == chat_channel
    assert args[1]["event"] == "typing"
    assert args[1]["user_id"] == str(user_id)
    assert args[1]["chat_id"] == str(chat_id)
    assert args[1]["is_typing"] == True


def test_get_chat_participants(test_manager):
    """Тест получения списка участников чата"""
    chat_id = uuid.uuid4()
    user_id1 = uuid.uuid4()
    user_id2 = uuid.uuid4()
    
    # Добавляем пользователей в чат
    test_manager.chat_participants[chat_id] = {user_id1, user_id2}
    
    # Получаем список участников
    participants = test_manager.get_chat_participants(chat_id)
    
    # Проверяем результат
    assert len(participants) == 2
    assert user_id1 in participants
    assert user_id2 in participants


def test_get_chat_participants_empty(test_manager):
    """Тест получения списка участников несуществующего чата"""
    chat_id = uuid.uuid4()
    
    # Получаем список участников
    participants = test_manager.get_chat_participants(chat_id)
    
    # Проверяем результат
    assert isinstance(participants, set)
    assert len(participants) == 0


def test_is_user_in_chat(test_manager):
    """Тест проверки наличия пользователя в чате"""
    chat_id = uuid.uuid4()
    user_id1 = uuid.uuid4()
    user_id2 = uuid.uuid4()
    
    # Добавляем одного пользователя в чат
    test_manager.chat_participants[chat_id] = {user_id1}
    
    # Проверяем наличие пользователей
    assert test_manager.is_user_in_chat(chat_id, user_id1) == True
    assert test_manager.is_user_in_chat(chat_id, user_id2) == False
    
    # Проверяем несуществующий чат
    non_existent_chat = uuid.uuid4()
    assert test_manager.is_user_in_chat(non_existent_chat, user_id1) == False


@pytest.mark.asyncio
async def test_send_personal_message_error_handling(test_manager, mock_centrifugo_client):
    """Тест обработки ошибок при отправке личного сообщения"""
    user_id = uuid.uuid4()
    message = {"event": "test_event", "data": "test_data"}
    
    # Настраиваем мок на генерацию исключения
    mock_centrifugo_client.publish.side_effect = Exception("Test exception")
    
    # Вызываем тестируемый метод
    result = await test_manager.send_personal_message(message, user_id)
    
    # Проверяем результат
    assert result == False
    
    # Проверяем, что метод публикации был вызван
    user_channel = mock_centrifugo_client.get_user_channel_name(str(user_id))
    mock_centrifugo_client.publish.assert_called_once_with(user_channel, message) 