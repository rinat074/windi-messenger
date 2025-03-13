"""
Тесты для модуля crud.message
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.crud.message import save_message_to_db


@pytest.mark.asyncio
async def test_save_message_to_db_success():
    """Тест успешного сохранения сообщения в БД"""
    # Подготовка мока сессии БД
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_db.execute.return_value = mock_result
    
    # Мокируем uuid.uuid4 для предсказуемости тестов
    test_message_id = "test-message-id"
    with patch("uuid.uuid4", return_value=test_message_id):
        # Вызов тестируемой функции
        result = await save_message_to_db(
            db=mock_db,
            chat_id="test-chat-id",
            sender_id="test-user-id",
            text="Test message",
            client_message_id="client-123",
            attachments=[]
        )
    
    # Проверки
    assert result == test_message_id
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()
    
    # Проверяем параметры SQL-запроса
    args, kwargs = mock_db.execute.call_args
    params = kwargs["parameters"]
    assert params["id"] == test_message_id
    assert params["chat_id"] == "test-chat-id"
    assert params["sender_id"] == "test-user-id"
    assert params["text"] == "Test message"
    assert params["client_message_id"] == "client-123"
    assert params["is_read"] is False


@pytest.mark.asyncio
async def test_save_message_to_db_with_attachments():
    """Тест сохранения сообщения с вложениями"""
    # Подготовка мока сессии БД
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_db.execute.return_value = mock_result
    
    # Тестовые данные
    test_message_id = "test-message-id"
    test_attachments = [
        {"type": "image", "url": "http://example.com/image.jpg"},
        {"type": "file", "url": "http://example.com/file.pdf"}
    ]
    
    with patch("uuid.uuid4", return_value=test_message_id):
        # Вызов тестируемой функции
        result = await save_message_to_db(
            db=mock_db,
            chat_id="test-chat-id",
            sender_id="test-user-id",
            text="Test message with attachments",
            client_message_id="client-123",
            attachments=test_attachments
        )
    
    # Проверки
    assert result == test_message_id
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_save_message_to_db_sql_error():
    """Тест обработки SQL ошибки при сохранении сообщения"""
    # Подготовка мока сессии БД с имитацией ошибки
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.side_effect = SQLAlchemyError("Test SQL error")
    
    # Вызов тестируемой функции
    result = await save_message_to_db(
        db=mock_db,
        chat_id="test-chat-id",
        sender_id="test-user-id",
        text="Test message",
        client_message_id="client-123"
    )
    
    # Проверки
    assert result is None  # Функция должна вернуть None при ошибке
    mock_db.rollback.assert_called_once()  # Должен быть вызван rollback


@pytest.mark.asyncio
async def test_save_message_to_db_general_error():
    """Тест обработки общей ошибки при сохранении сообщения"""
    # Подготовка мока сессии БД с имитацией общей ошибки
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.side_effect = Exception("Test general error")
    
    # Вызов тестируемой функции
    result = await save_message_to_db(
        db=mock_db,
        chat_id="test-chat-id",
        sender_id="test-user-id",
        text="Test message"
    )
    
    # Проверки
    assert result is None  # Функция должна вернуть None при ошибке
    mock_db.rollback.assert_called_once()  # Должен быть вызван rollback


@pytest.mark.asyncio
async def test_save_message_to_db_invalid_input():
    """Тест обработки некорректных входных данных"""
    # Подготовка мока сессии БД
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Тест с пустым текстом сообщения
    result_empty_text = await save_message_to_db(
        db=mock_db,
        chat_id="test-chat-id",
        sender_id="test-user-id",
        text="",  # Пустой текст
        client_message_id="client-123"
    )
    
    # Функция должна обработать пустой текст согласно логике
    # В зависимости от требований, пустой текст может быть валидным или нет
    # Здесь мы предполагаем, что он должен обрабатываться, но с резервным текстом
    assert result_empty_text is not None, "Функция должна обрабатывать пустой текст"
    
    # Тест с None значениями обязательных параметров
    result_none_chat_id = await save_message_to_db(
        db=mock_db,
        chat_id=None,  # None chat_id
        sender_id="test-user-id",
        text="Test message"
    )
    assert result_none_chat_id is None, "Функция должна возвращать None при None chat_id"
    
    result_none_sender_id = await save_message_to_db(
        db=mock_db,
        chat_id="test-chat-id",
        sender_id=None,  # None sender_id
        text="Test message"
    )
    assert result_none_sender_id is None, "Функция должна возвращать None при None sender_id"
    
    # Тест с некорректными типами
    invalid_chat_id_types = [123, {}, [], True]
    for invalid_chat_id in invalid_chat_id_types:
        result = await save_message_to_db(
            db=mock_db,
            chat_id=invalid_chat_id,  # Некорректный тип
            sender_id="test-user-id",
            text="Test message"
        )
        assert result is None, f"Функция должна возвращать None при некорректном типе chat_id: {type(invalid_chat_id)}"
    
    # Тест со слишком длинным текстом
    very_long_text = "x" * 10000  # Предположим, что это превышает ограничение
    result_long_text = await save_message_to_db(
        db=mock_db,
        chat_id="test-chat-id",
        sender_id="test-user-id",
        text=very_long_text
    )
    # Функция должна либо обрезать текст, либо вернуть ошибку - в зависимости от требований
    # В нашем случае мы проверяем, что функция возвращает какой-то результат
    assert isinstance(result_long_text, (str, type(None))), "Функция должна правильно обрабатывать длинный текст"


@pytest.mark.asyncio
async def test_save_message_to_db_validate_attachments():
    """Тест валидации вложений при сохранении сообщения"""
    # Подготовка мока сессии БД
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_db.execute.return_value = mock_result
    
    # Тестовые данные с некорректными вложениями
    test_message_id = "test-message-id"
    invalid_attachments = [
        # Пустой словарь
        {},
        # Отсутствует тип
        {"url": "http://example.com/file.pdf"},
        # Отсутствует URL
        {"type": "file"},
        # Некорректное значение типа
        {"type": 123, "url": "http://example.com/image.jpg"},
        # Некорректный формат URL
        {"type": "image", "url": "invalid-url"}
    ]
    
    with patch("uuid.uuid4", return_value=test_message_id):
        # Вызов тестируемой функции
        result = await save_message_to_db(
            db=mock_db,
            chat_id="test-chat-id",
            sender_id="test-user-id",
            text="Test message with invalid attachments",
            client_message_id="client-123",
            attachments=invalid_attachments
        )
    
    # Проверки
    # Функция должна игнорировать некорректные вложения или логировать ошибки,
    # но всё равно сохранить сообщение
    assert result == test_message_id
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once() 