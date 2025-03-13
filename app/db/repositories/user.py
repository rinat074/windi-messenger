from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.user import User
from app.db.repositories.base import BaseRepository

# Получение логгера
logger = get_logger("user_repository")


class UserRepository(BaseRepository):
    """Репозиторий для работы с пользователями"""
    
    def __init__(self, db: AsyncSession):
        """
        Инициализация репозитория пользователей
        
        Args:
            db: Сессия базы данных
        """
        super().__init__(db, User)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Получение пользователя по email
        
        Args:
            email: Email пользователя
            
        Returns:
            Найденный пользователь или None, если пользователь не найден
        """
        logger.debug(f"Поиск пользователя с email: {email}")
        result = await self.db.execute(select(User).filter(User.email == email))
        return result.scalar_one_or_none() 