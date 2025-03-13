"""
Общие фикстуры для тестов

Этот модуль содержит общие фикстуры, которые могут использоваться во всех тестах проекта.
Фикстуры включают:
- Настройку тестовой базы данных
- Моки для различных компонентов (БД, HTTP клиент, Centrifugo)
- Тестовые данные для пользователей, чатов и сообщений

Для запуска тестов с реальной БД установите переменную окружения:
TEST_DATABASE_URL=postgresql+asyncpg://user:password@host:port/test_db

Для разрешения использования локальной БД для тестов:
ALLOW_LOCAL_DB_FOR_TESTS=1
"""
import os
import pytest
import asyncio
import warnings
import logging
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.database import get_db
from app.core.centrifugo import CentrifugoClient


# Настройка логирования для тестов
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("tests")


# Фикстура для переопределения петли событий для async тестов
@pytest.fixture
def event_loop():
    """Создает новую петлю событий для каждого теста"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Мок асинхронной сессии БД
@pytest.fixture
def mock_db_session():
    """Создает мок для асинхронной сессии БД"""
    mock = AsyncMock(spec=AsyncSession)
    return mock


# Фикстура для создания реальной тестовой асинхронной сессии БД
@pytest.fixture
async def db_session():
    """
    Создает реальную асинхронную сессию БД для тестов
    
    Эта фикстура создает временную базу данных со структурой, необходимой
    для тестирования, и заполняет её тестовыми данными. После выполнения
    тестов данные очищаются.
    
    Примечание: Для CI/CD рекомендуется использовать выделенную тестовую БД.
    """
    # Берем URL из окружения или используем тестовый URL по умолчанию
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test_db"
    )
    
    # Предупреждение о локальной БД
    if "localhost" in test_db_url and not os.environ.get("ALLOW_LOCAL_DB_FOR_TESTS"):
        warnings.warn(
            "Используется локальная БД для тестов. Установите ALLOW_LOCAL_DB_FOR_TESTS=1, "
            "если это намеренно, или настройте TEST_DATABASE_URL для CI."
        )
    
    # Логируем информацию о подключении (без пароля)
    safe_url = test_db_url.split("@")[-1]
    logger.info(f"Подключение к тестовой БД: ...@{safe_url}")
    
    try:
        # Создаем движок и сессию
        engine = create_async_engine(test_db_url, pool_pre_ping=True)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Проверяем соединение
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("Соединение с БД установлено успешно")
        
        # Создаем тестовые таблицы и данные
        async with engine.begin() as conn:
            await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            )
            """))
            
            await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chats (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """))
            
            await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_users (
                chat_id VARCHAR(36) REFERENCES chats(id),
                user_id VARCHAR(36) REFERENCES users(id),
                PRIMARY KEY (chat_id, user_id)
            )
            """))
            
            await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id VARCHAR(36) PRIMARY KEY,
                chat_id VARCHAR(36) REFERENCES chats(id),
                sender_id VARCHAR(36) REFERENCES users(id),
                text TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                client_message_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """))
            
            # Таблица для вложений
            await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS attachments (
                id VARCHAR(36) PRIMARY KEY,
                message_id VARCHAR(36) REFERENCES messages(id) ON DELETE CASCADE,
                type VARCHAR(50) NOT NULL,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """))
        
        # Создаем тестового пользователя и чат
        async with async_session() as session:
            await session.execute(text("""
            INSERT INTO users (id, name, email, password, is_active)
            VALUES ('test-user-id', 'Test User', 'test@example.com', 'hashed_password', TRUE)
            ON CONFLICT DO NOTHING
            """))
            
            await session.execute(text("""
            INSERT INTO chats (id, name)
            VALUES ('test-chat-id', 'Test Chat')
            ON CONFLICT DO NOTHING
            """))
            
            await session.execute(text("""
            INSERT INTO chat_users (chat_id, user_id)
            VALUES ('test-chat-id', 'test-user-id')
            ON CONFLICT DO NOTHING
            """))
            
            await session.commit()
        
        # Создаем и отдаем сессию
        async with async_session() as session:
            yield session
        
        # Чистим данные после тестов
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM attachments"))
            await conn.execute(text("DELETE FROM messages"))
            await conn.execute(text("DELETE FROM chat_users"))
            await conn.execute(text("DELETE FROM chats"))
            await conn.execute(text("DELETE FROM users"))
        
        # Закрываем соединение
        await engine.dispose()
        logger.info("Соединение с БД закрыто")
        
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при настройке тестовой БД: {str(e)}")
        pytest.skip(f"Не удалось подключиться к тестовой БД: {str(e)}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при настройке тестовой БД: {str(e)}")
        pytest.skip(f"Ошибка настройки тестовой БД: {str(e)}")


# Переопределяем функцию get_db для тестирования
@pytest.fixture
def override_get_db(db_session):
    """Переопределяет функцию get_db для тестов"""
    async def _get_db():
        yield db_session
    
    return _get_db


# Мок для httpx.AsyncClient
@pytest.fixture
def mock_httpx_client():
    """Создает мок для httpx.AsyncClient"""
    mock = AsyncMock(spec=httpx.AsyncClient)
    
    # Настройка успешного ответа для post
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {}}
    mock.post.return_value = mock_response
    
    # Настройка успешного ответа для get
    mock.get.return_value = mock_response
    
    with patch("httpx.AsyncClient", return_value=mock):
        yield mock


# Мок для Centrifugo клиента
@pytest.fixture
def mock_centrifugo_client():
    """Создает мок для Centrifugo клиента"""
    mock = AsyncMock(spec=CentrifugoClient)
    
    # Настройка успешных ответов для методов
    mock.generate_connection_token.return_value = "mock-centrifugo-token"
    mock.publish.return_value = {"result": {}}
    mock.presence.return_value = {
        "result": {
            "presence": {
                "test-user-id": {"client": "test-client", "user": "test-user"}
            }
        }
    }
    mock.get_chat_channel_name.return_value = "chat:test-chat-id"
    
    with patch("app.core.centrifugo.centrifugo_client", mock):
        yield mock


# Фикстура для тестов с токеном авторизации
@pytest.fixture
def auth_headers():
    """Создает заголовки с токеном авторизации для тестов"""
    return {"Authorization": f"Bearer test-token"}


# Фикстура для тестирования чата
@pytest.fixture
def test_chat_data():
    """Возвращает тестовые данные чата"""
    return {
        "id": "test-chat-id",
        "name": "Test Chat",
        "participants": ["test-user-id"]
    }


# Фикстура для тестирования сообщений
@pytest.fixture
def test_message_data():
    """Возвращает тестовые данные сообщения"""
    return {
        "id": "test-message-id",
        "chat_id": "test-chat-id",
        "sender_id": "test-user-id",
        "text": "Test message",
        "client_message_id": "client-123",
        "is_read": False,
        "created_at": "2023-01-01T12:00:00"
    } 