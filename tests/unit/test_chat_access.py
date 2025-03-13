"""
Тесты для модуля crud.chat
"""
import pytest
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.crud.chat import check_chat_access, is_user_in_chat


@pytest.mark.asyncio
async def test_check_chat_access_success():
    """Тест успешной проверки доступа к чату"""
    # Настройка мока для db.execute
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_result.scalar.return_value = 1
    mock_db.execute.return_value = mock_result
    
    # Вызов тестируемой функции
    result = await check_chat_access(
        db=mock_db,
        user_id="test-user-id",
        chat_id="test-chat-id"
    )
    
    # Проверки
    assert result is True
    mock_db.execute.assert_called_once()
    # Проверяем, что запрос содержит правильные параметры
    args, kwargs = mock_db.execute.call_args
    assert "user_id" in kwargs["parameters"]
    assert "chat_id" in kwargs["parameters"]
    assert kwargs["parameters"]["user_id"] == "test-user-id"
    assert kwargs["parameters"]["chat_id"] == "test-chat-id"


@pytest.mark.asyncio
async def test_check_chat_access_no_access():
    """Тест проверки отсутствия доступа к чату"""
    # Настройка мока для db.execute
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_result.scalar.return_value = 0  # Нет доступа
    mock_db.execute.return_value = mock_result
    
    # Вызов тестируемой функции
    result = await check_chat_access(
        db=mock_db,
        user_id="test-user-id",
        chat_id="test-chat-id"
    )
    
    # Проверки
    assert result is False


@pytest.mark.asyncio
async def test_check_chat_access_db_error():
    """Тест обработки ошибки базы данных"""
    # Настройка мока для db.execute, чтобы он вызывал ошибку
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute.side_effect = SQLAlchemyError("Test database error")
    
    # Вызов тестируемой функции должен обработать ошибку
    result = await check_chat_access(
        db=mock_db,
        user_id="test-user-id",
        chat_id="test-chat-id"
    )
    
    # Проверки
    assert result is False  # Функция должна вернуть False при ошибке


@pytest.mark.asyncio
async def test_is_user_in_chat_calls_check_chat_access():
    """Тест проверки, что is_user_in_chat вызывает check_chat_access"""
    # Используем патч для проверки, что is_user_in_chat вызывает check_chat_access
    with patch("app.db.crud.chat.check_chat_access") as mock_check_chat_access:
        mock_check_chat_access.return_value = True
        mock_db = AsyncMock(spec=AsyncSession)
        
        # Вызов тестируемой функции
        result = await is_user_in_chat(
            db=mock_db,
            user_id="test-user-id",
            chat_id="test-chat-id"
        )
        
        # Проверки
        assert result is True
        mock_check_chat_access.assert_called_once_with(
            mock_db, "test-user-id", "test-chat-id"
        )


@pytest.mark.parametrize("scalar_value,expected", [
    (1, True),   # Есть доступ
    (0, False),  # Нет доступа
    (None, False)  # Нет данных - нет доступа
])
@pytest.mark.asyncio
async def test_check_chat_access_parameterized(scalar_value, expected):
    """Параметризованный тест проверки доступа к чату с разными результатами"""
    # Настройка мока для db.execute
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_result.scalar.return_value = scalar_value
    mock_db.execute.return_value = mock_result
    
    # Вызов тестируемой функции
    result = await check_chat_access(
        db=mock_db,
        user_id="test-user-id",
        chat_id="test-chat-id"
    )
    
    # Проверки
    assert result is expected
    mock_db.execute.assert_called_once()
    

@pytest.mark.asyncio
async def test_check_chat_access_with_various_errors():
    """Тест обработки различных типов ошибок при проверке доступа"""
    # Тестируем разные типы исключений
    error_types = [
        SQLAlchemyError("Ошибка SQL"),
        ConnectionError("Ошибка соединения"),
        Exception("Общая ошибка")
    ]
    
    for error in error_types:
        # Настройка мока для вызова ошибки
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute.side_effect = error
        
        # Вызов тестируемой функции должен обработать ошибку
        result = await check_chat_access(
            db=mock_db,
            user_id="test-user-id",
            chat_id="test-chat-id"
        )
        
        # Функция должна вернуть False при любой ошибке
        assert result is False, f"Ошибка {type(error).__name__} должна быть обработана" 