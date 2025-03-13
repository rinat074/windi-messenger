"""
Операции CRUD для сообщений
"""
import uuid
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger

# Получение логгера
logger = get_logger("crud.message")

async def save_message_to_db(
    db: AsyncSession, 
    chat_id: str,
    sender_id: str,
    text: str,
    client_message_id: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> Optional[str]:
    """
    Сохраняет сообщение в базу данных
    
    Args:
        db: Сессия базы данных
        chat_id: ID чата
        sender_id: ID отправителя
        text: Текст сообщения
        client_message_id: Клиентский ID сообщения
        attachments: Список вложений
        
    Returns:
        Optional[str]: ID созданного сообщения или None в случае ошибки
    """
    try:
        # Создаем запись о сообщении
        query = text("""
        INSERT INTO messages (id, chat_id, sender_id, text, is_read, client_message_id, created_at, updated_at)
        VALUES (:id, :chat_id, :sender_id, :text, :is_read, :client_message_id, :created_at, :created_at)
        RETURNING id
        """)
        
        message_id = str(uuid.uuid4())
        now = datetime.now()
        
        result = await db.execute(
            query, 
            {
                "id": message_id,
                "chat_id": chat_id,
                "sender_id": sender_id,
                "text": text,
                "is_read": False,
                "client_message_id": client_message_id,
                "created_at": now
            }
        )
        
        # Если есть вложения, сохраняем их
        if attachments:
            for attachment in attachments:
                # Тут должна быть логика сохранения вложений
                pass
        
        await db.commit()
        
        logger.info(f"Сообщение {message_id} сохранено в базе данных")
        return message_id
    
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Ошибка SQL при сохранении сообщения в БД: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при сохранении сообщения в БД: {str(e)}", exc_info=True)
        return None 