"""
Интеграционные тесты для Centrifugo

Эти тесты проверяют интеграцию между компонентами:
- Centrifugo клиент
- БД операции для сообщений и чатов
- API эндпоинты для работы с Centrifugo
"""
import pytest
import asyncio
import contextlib
from unittest.mock import patch, AsyncMock

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.centrifugo import centrifugo_client
from app.api.routes.centrifugo_routes import router as centrifugo_router
from app.db.crud.chat import check_chat_access
from app.db.crud.message import save_message_to_db

# Вспомогательные функции для тестов
def verify_publish_not_called(mock_client):
    """Проверяет, что метод publish не был вызван"""
    mock_client.publish.assert_not_called()
    mock_client.publish.reset_mock()

async def verify_message_in_db(db_session, message_id, expected_text):
    """Проверяет наличие сообщения в БД с ожидаемым текстом"""
    from sqlalchemy import text
    try:
        result = await db_session.execute(
            text("SELECT * FROM messages WHERE id = :message_id"),
            {"message_id": message_id}
        )
        message = result.fetchone()
        
        assert message is not None, f"Сообщение с ID {message_id} не найдено в БД"
        assert message.text == expected_text, f"Текст сообщения не соответствует ожидаемому"
        return message
    except Exception as e:
        pytest.fail(f"Ошибка при проверке сообщения в БД: {str(e)}")

# Создаем тестовое приложение FastAPI
@pytest.fixture
def test_app():
    """Создает тестовое приложение FastAPI"""
    app = FastAPI()
    app.include_router(centrifugo_router)
    return app


@pytest.fixture
def test_client(test_app):
    """Создает тестовый клиент для приложения"""
    return TestClient(test_app)


# Вспомогательная функция для управления транзакциями в тестах
@contextlib.asynccontextmanager
async def managed_transaction(db_session):
    """
    Контекстный менеджер для управления транзакциями в тестах
    
    Создает новую транзакцию для теста и автоматически откатывает её после выполнения,
    чтобы избежать влияния тестов друг на друга.
    """
    # Начинаем транзакцию
    async with db_session.begin() as transaction:
        try:
            yield transaction
        except Exception as e:
            pytest.fail(f"Ошибка во время выполнения теста: {str(e)}")
        finally:
            # В любом случае откатываем транзакцию
            await transaction.rollback()


@pytest.mark.asyncio
async def test_chat_access_integration(db_session):
    """Интеграционный тест для проверки доступа к чату"""
    # Используем транзакцию для изоляции теста
    async with managed_transaction(db_session):
        try:
            # Проверка доступа пользователя к чату
            result = await check_chat_access(
                db=db_session,
                user_id="test-user-id",
                chat_id="test-chat-id"
            )
            assert result is True
            
            # Проверка отсутствия доступа
            result = await check_chat_access(
                db=db_session,
                user_id="non-existent-user",
                chat_id="test-chat-id"
            )
            assert result is False
        except Exception as e:
            pytest.fail(f"Ошибка при проверке доступа к чату: {str(e)}")


@pytest.mark.asyncio
async def test_save_message_integration(db_session):
    """Интеграционный тест для сохранения сообщения"""
    # Используем транзакцию для изоляции теста
    async with managed_transaction(db_session):
        try:
            # Сохраняем тестовое сообщение
            message_id = await save_message_to_db(
                db=db_session,
                chat_id="test-chat-id",
                sender_id="test-user-id",
                text="Интеграционный тест сообщения",
                client_message_id="integration-test-123"
            )
            
            assert message_id is not None
            
            # Проверяем, что сообщение сохранилось в БД
            await verify_message_in_db(
                db_session, 
                message_id, 
                "Интеграционный тест сообщения"
            )
        except Exception as e:
            pytest.fail(f"Ошибка при сохранении сообщения: {str(e)}")


@pytest.mark.asyncio
async def test_save_message_with_attachments_integration(db_session):
    """Интеграционный тест для сохранения сообщения с вложениями"""
    # Используем транзакцию для изоляции теста
    async with managed_transaction(db_session):
        # Создаем тестовые вложения
        attachments = [
            {"type": "image", "url": "http://example.com/image.jpg"},
            {"type": "file", "url": "http://example.com/document.pdf"}
        ]
        
        # Сохраняем тестовое сообщение с вложениями
        message_id = await save_message_to_db(
            db=db_session,
            chat_id="test-chat-id",
            sender_id="test-user-id",
            text="Интеграционный тест сообщения с вложениями",
            client_message_id="integration-test-attachments-123",
            attachments=attachments
        )
        
        assert message_id is not None
        
        # Проверяем, что сообщение сохранилось в БД
        from sqlalchemy import text
        result = await db_session.execute(
            text("SELECT * FROM messages WHERE id = :message_id"),
            {"message_id": message_id}
        )
        message = result.fetchone()
        
        assert message is not None
        assert message.text == "Интеграционный тест сообщения с вложениями"
        
        # Проверяем, что вложения сохранились
        result = await db_session.execute(
            text("SELECT * FROM attachments WHERE message_id = :message_id"),
            {"message_id": message_id}
        )
        attachments_result = result.fetchall()
        
        # Должно быть 2 вложения
        assert len(attachments_result) == 2
        
        # Проверяем типы вложений
        attachment_types = [a.type for a in attachments_result]
        assert "image" in attachment_types
        assert "file" in attachment_types


@pytest.mark.asyncio
async def test_centrifugo_client_integration(mock_httpx_client):
    """Интеграционный тест для клиента Centrifugo"""
    # Тестируем генерацию токена
    token = centrifugo_client.generate_connection_token(
        user_id="test-user-id",
        user_name="Test User"
    )
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 10  # Токен должен быть непустой строкой разумной длины
    
    # Тестируем публикацию сообщения
    result = await centrifugo_client.publish(
        channel="chat:test-chat-id",
        data={
            "text": "Тестовое сообщение",
            "sender_id": "test-user-id",
            "sender_name": "Test User"
        }
    )
    assert result is not None
    
    # Проверяем вызов httpx.AsyncClient.post
    mock_httpx_client.post.assert_called()
    
    # Проверяем параметры вызова
    args, kwargs = mock_httpx_client.post.call_args
    assert "channel" in kwargs.get("json", {})
    assert kwargs.get("json", {}).get("channel") == "chat:test-chat-id"
    assert "data" in kwargs.get("json", {})


@pytest.mark.parametrize("channel,message_text,expected_status", [
    ("chat:test-chat-id", "Обычное сообщение", 200),
    ("chat:non-existent", "Недоступный чат", 403),
    ("user:test-user-id", "Персональное сообщение", 200),
    ("invalid-channel-format", "Некорректный формат канала", 400),
])
@pytest.mark.asyncio
async def test_publish_message_endpoint(
    test_app, channel, message_text, expected_status, 
    mock_centrifugo_client, override_get_db
):
    """
    Тест эндпоинта публикации сообщений
    
    Проверяет различные сценарии публикации сообщений через API:
    - Публикация в доступный чат
    - Попытка публикации в недоступный чат
    - Публикация в персональный канал пользователя
    - Попытка публикации в канал с некорректным форматом
    
    Для каждого сценария проверяется ожидаемый HTTP-статус ответа и 
    вызов нужных методов клиента Centrifugo.
    """
    # Патчим зависимости
    with patch("app.api.routes.centrifugo_routes.get_db", return_value=override_get_db), \
         patch("app.api.routes.centrifugo_routes.get_current_user") as mock_user:
        
        # Мокируем текущего пользователя
        user = AsyncMock()
        user.id = "test-user-id"
        user.name = "Test User"
        mock_user.return_value = user
        
        # Для некорректного формата канала
        if channel == "invalid-channel-format":
            # Проверяем валидацию формата канала в API
            async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/centrifugo/publish",
                    params={"channel": channel},
                    json={"text": message_text, "type": "message"}
                )
                assert response.status_code == expected_status
                # Убеждаемся, что publish не вызывался для некорректного канала
                verify_publish_not_called(mock_centrifugo_client)
        # Если канал недоступного чата - мокируем check_chat_access для возврата False
        elif channel == "chat:non-existent":
            with patch("app.db.crud.chat.check_chat_access", return_value=False):
                async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/centrifugo/publish",
                        params={"channel": channel},
                        json={"text": message_text, "type": "message"}
                    )
                    assert response.status_code == expected_status
                    # Убеждаемся, что publish не вызывался для недоступного чата
                    verify_publish_not_called(mock_centrifugo_client)
        else:
            # Для остальных каналов
            with patch("app.db.crud.chat.check_chat_access", return_value=True):
                async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/centrifugo/publish",
                        params={"channel": channel},
                        json={"text": message_text, "type": "message"}
                    )
                    assert response.status_code == expected_status
                    
                    # Проверяем, что публикация была вызвана для успешных запросов
                    if expected_status == 200:
                        mock_centrifugo_client.publish.assert_called()
                        
                        # Проверяем правильность параметров
                        args, kwargs = mock_centrifugo_client.publish.call_args
                        assert args[0] == channel  # Первый позиционный аргумент - канал
                        assert "text" in kwargs.get("data", {})
                        assert kwargs.get("data", {}).get("text") == message_text


@pytest.mark.asyncio
async def test_message_flow_integration(
    db_session, mock_centrifugo_client, override_get_db
):
    """
    Интеграционный тест полного потока работы с сообщениями
    
    Тестирует весь путь сообщения:
    1. Сохранение в БД
    2. Публикация в Centrifugo
    3. Проверка истории сообщений
    """
    # Используем транзакцию для изоляции теста
    async with managed_transaction(db_session):
        # 1. Сохраняем сообщение в БД
        message_text = "Интеграционный тест полного потока"
        message_id = await save_message_to_db(
            db=db_session,
            chat_id="test-chat-id",
            sender_id="test-user-id",
            text=message_text,
            client_message_id="flow-test-123"
        )
        
        assert message_id is not None
        
        # 2. Публикуем сообщение в Centrifugo
        chat_channel = f"chat:test-chat-id"
        publish_result = await centrifugo_client.publish(
            channel=chat_channel,
            data={
                "id": message_id,
                "text": message_text,
                "sender_id": "test-user-id",
                "chat_id": "test-chat-id",
                "created_at": "2023-01-01T12:00:00"  # Для тестирования используем фиксированную дату
            }
        )
        
        assert publish_result is not None
        
        # 3. Имитируем загрузку истории сообщений из БД
        from sqlalchemy import text
        result = await db_session.execute(
            text("SELECT * FROM messages WHERE chat_id = :chat_id ORDER BY created_at DESC LIMIT 10"),
            {"chat_id": "test-chat-id"}
        )
        messages = result.fetchall()
        
        # Проверяем, что наше сообщение есть в истории
        assert any(m.id == message_id for m in messages)
        assert any(m.text == message_text for m in messages) 