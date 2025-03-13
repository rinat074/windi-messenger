"""
Операции CRUD для работы с чатами
"""

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger

# Получение логгера
logger = get_logger("crud.chat")


async def is_user_in_chat(db: AsyncSession, user_id: str, chat_id: str) -> bool:
    """
    Проверяет, является ли пользователь участником чата
    
    Args:
        db: Сессия базы данных
        user_id: ID пользователя
        chat_id: ID чата
        
    Returns:
        bool: True, если пользователь является участником чата
    """
    return await check_chat_access(db, user_id, chat_id)


async def check_chat_access(db: AsyncSession, user_id: str, chat_id: str) -> bool:
    """
    Проверяет доступ пользователя к чату
    
    Args:
        db: Сессия базы данных
        user_id: ID пользователя
        chat_id: ID чата
        
    Returns:
        bool: True, если пользователь имеет доступ к чату
    """
    try:
        query = text("""
        SELECT COUNT(*) FROM chat_users 
        WHERE user_id = :user_id AND chat_id = :chat_id
        """)
        result = await db.execute(query, {"user_id": user_id, "chat_id": chat_id})
        count = result.scalar()
        
        return count > 0
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQL при проверке доступа к чату: {str(e)}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке доступа к чату: {str(e)}", exc_info=True)
        return False 