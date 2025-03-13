import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

from app.core.config import settings

# Получение логгера
logger = logging.getLogger(__name__)

# Создание асинхронного движка SQLAlchemy
engine = create_async_engine(
    settings.DATABASE_URI,
    echo=True,  # Логирование SQL-запросов (в продакшене лучше отключить)
    future=True,
)

# Создание фабрики асинхронных сессий
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autocommit=False, 
    autoflush=False
)

# Базовый класс для всех моделей
Base = declarative_base()

# Функция для инициализации БД
async def init_db():
    """
    Инициализация базы данных при запуске приложения
    - Создание таблиц, если они не существуют
    - Применение миграций Alembic (в продакшене)
    """
    try:
        # В режиме разработки можно создавать таблицы напрямую
        if os.environ.get("APP_ENV") == "development":
            logger.info("Создание таблиц базы данных (режим разработки)")
            async with engine.begin() as conn:
                # Создание всех таблиц в моделях, импортированных в этот момент
                from app.db.models import User, Chat, Message  # для загрузки моделей
                await conn.run_sync(Base.metadata.create_all)
        else:
            # В продакшене используем миграции Alembic
            logger.info("Применение миграций Alembic (продакшен)")
            # Тут можно добавить автоматическое применение миграций
            # Например, вызвать скрипт alembic через subprocess
            
            # Для тестирования, пока оставим простое создание таблиц
            async with engine.begin() as conn:
                # Создание всех таблиц в моделях, импортированных в этот момент
                from app.db.models import User, Chat, Message  # для загрузки моделей
                await conn.run_sync(Base.metadata.create_all)
                
        logger.info("Инициализация базы данных завершена")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise

# Функция для получения сессии БД
async def get_db():
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close() 