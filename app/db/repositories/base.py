from typing import Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

# Создаем типизированную переменную для моделей
T = TypeVar('T')

# Получение логгера
logger = get_logger("base_repository")


class BaseRepository:
    """Базовый репозиторий с общими методами для всех моделей"""
    
    def __init__(self, db: AsyncSession, model: Type[T]):
        """
        Инициализация репозитория
        
        Args:
            db: Сессия базы данных
            model: Класс модели, с которой работает репозиторий
        """
        self.db = db
        self.model = model
    
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """
        Получение объекта по его ID
        
        Args:
            id: Идентификатор объекта
            
        Returns:
            Найденный объект или None, если объект не найден
        """
        result = await self.db.execute(select(self.model).filter(self.model.id == id))
        return result.scalar_one_or_none()
    
    async def create(self, obj_in) -> T:
        """
        Создание нового объекта
        
        Args:
            obj_in: Pydantic схема с данными объекта
            
        Returns:
            Созданный объект
        """
        obj_data = obj_in.dict()
        db_obj = self.model(**obj_data)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj 