from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, get_password_hash, verify_password
from app.core.logging import get_logger
from app.core.performance import async_time_it, AsyncPerformanceTracker
from app.db.models.user import User
from app.db.repositories.user import UserRepository
from app.schemas.user import UserCreate

# Получение логгера
logger = get_logger(__name__)


class UserService:
    """Сервис для работы с пользователями"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
    
    @async_time_it
    async def create_user(self, user_in: UserCreate) -> User:
        """Создание нового пользователя"""
        # Проверка наличия пользователя с таким email
        async with AsyncPerformanceTracker("Проверка существования email"):
            user = await self.user_repo.get_by_email(user_in.email)
            if user:
                logger.warning(f"Попытка создать пользователя с существующим email: {user_in.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь с таким email уже существует"
                )
        
        # Хеширование пароля
        hashed_password = get_password_hash(user_in.password)
        
        # Создание пользователя
        user = User(
            name=user_in.name,
            email=user_in.email,
            password_hash=hashed_password
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"Создан новый пользователь: {user.email}")
        return user
    
    @async_time_it
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Аутентификация пользователя"""
        async with AsyncPerformanceTracker("Получение пользователя по email"):
            user = await self.user_repo.get_by_email(email)
            if not user:
                logger.warning(f"Попытка аутентификации с несуществующим email: {email}")
                return None
        
        async with AsyncPerformanceTracker("Проверка пароля"):
            if not verify_password(password, user.password_hash):
                logger.warning(f"Попытка аутентификации с неверным паролем для пользователя: {email}")
                return None
        
        logger.info(f"Успешная аутентификация пользователя: {email}")
        return user
    
    def create_access_token(self, user_id: UUID) -> str:
        """Создание JWT токена доступа"""
        return create_access_token(user_id) 