from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_token, get_current_user_from_token as auth_get_user, oauth2_scheme
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models.user import User
from app.schemas.user import UserResponse

# Получение логгера
logger = get_logger("dependencies")

# Схема OAuth2 для получения токенов
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/users/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Получает текущего пользователя по токену
    
    Args:
        token: JWT-токен авторизации
        db: Сессия базы данных
        
    Returns:
        User: Модель пользователя
        
    Raises:
        HTTPException: Если токен недействителен или пользователь не найден
    """
    # Верифицируем токен
    success, token_data, error = await decode_token(token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Недействительные учетные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Получаем пользователя из базы данных
    try:
        user = await db.get(User, token_data.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Проверяем, что пользователь активен
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь неактивен",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
    
    except Exception as e:
        logger.error(f"Ошибка при получении пользователя: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка при получении данных пользователя",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_response(
    user: User = Depends(get_current_user)
) -> UserResponse:
    """
    Получение текущего аутентифицированного пользователя (схема ответа)
    
    Args:
        user: Модель пользователя
        
    Returns:
        UserResponse: Схема ответа с данными пользователя
    """
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email
    )


async def get_current_user_from_token(
    token: str,
    db: AsyncSession
) -> Optional[User]:
    """
    Получение пользователя из токена для WebSocket соединений
    
    Args:
        token: JWT токен
        db: Сессия базы данных
        
    Returns:
        Optional[User]: Объект пользователя или None, если токен невалиден
    """
    return await auth_get_user(token, db)


async def admin_only(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Проверяет, что текущий пользователь имеет права администратора
    
    Args:
        current_user: Текущий пользователь
        
    Returns:
        User: Текущий пользователь с правами администратора
        
    Raises:
        HTTPException: Если у пользователя нет прав администратора
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен. Необходимы права администратора",
        )
    
    return current_user 