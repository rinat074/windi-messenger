"""
Маршруты для интеграции с Centrifugo
"""
from datetime import datetime
from typing import Dict, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.core.performance import async_time_it
from app.core.metrics import track_websocket_message
from app.db.database import get_db
from app.db.models.user import User
from app.core.centrifugo import centrifugo_client
from app.db.crud.chat import is_user_in_chat, check_chat_access
from app.db.crud.message import save_message_to_db
from app.schemas.user import UserOut
from app.schemas.token import TokenResponse

# Создание маршрутизатора
router = APIRouter(prefix=f"{settings.API_V1_STR}/centrifugo", tags=["centrifugo"])

# Получение логгера
logger = get_logger("centrifugo_routes")


@router.post("/connect", summary="Проксирование подключения к Centrifugo")
@async_time_it
async def centrifugo_connect(
    request: Request,
    data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Обработчик прокси-запросов подключения к Centrifugo
    
    Этот эндпоинт вызывается Centrifugo при каждом новом подключении клиента
    для проверки аутентификации и получения информации о пользователе.
    """
    logger.debug(f"Получен запрос на подключение к Centrifugo: {data}")
    
    try:
        # Получаем user_id из клейма токена
        user_id = data.get("user", {}).get("user_id")
        if not user_id:
            logger.warning("Попытка подключения без user_id")
            return {"status": 401, "disconnect": True}
        
        # Проверяем пользователя в базе данных
        query = text("SELECT id, name, email, is_active FROM users WHERE id = :user_id")
        result = await db.execute(query, {"user_id": user_id})
        user_row = result.fetchone()
        
        if not user_row or not user_row.is_active:
            logger.warning(f"Пользователь не найден или неактивен: {user_id}")
            return {"status": 403, "disconnect": True}
        
        # Формируем информацию о пользователе для Centrifugo
        user_info = {
            "id": str(user_row.id),
            "name": user_row.name,
            "email": user_row.email
        }
        
        logger.info(f"Пользователь {user_row.name} ({user_id}) подключился к Centrifugo")
        
        return {
            "result": {
                "user": user_info
            }
        }
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса на подключение: {str(e)}", exc_info=True)
        return {"status": 500, "disconnect": True}


@router.post("/subscribe", summary="Проксирование подписки на канал Centrifugo")
@async_time_it
async def centrifugo_subscribe(
    request: Request,
    data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Обработчик прокси-запросов подписки на каналы Centrifugo
    
    Этот эндпоинт вызывается Centrifugo когда клиент пытается подписаться на канал,
    позволяя вам проверить, имеет ли клиент доступ к этому каналу.
    """
    logger.debug(f"Получен запрос на подписку: {data}")
    
    try:
        # Получаем данные запроса
        client = data.get("client", {})
        user_id = client.get("user")
        channel = data.get("channel", "")
        
        if not user_id:
            logger.warning(f"Попытка подписки без user_id на канал {channel}")
            return {"status": 401}
        
        # Проверяем доступ пользователя к каналу
        # Канал чата должен иметь формат "chat:UUID"
        if channel.startswith("chat:"):
            chat_id = channel.split(":", 1)[1]
            
            # Проверяем, является ли пользователь участником чата
            has_access = await check_chat_access(db, user_id, chat_id)
            
            if not has_access:
                logger.warning(f"Пользователь {user_id} не имеет доступа к чату {chat_id}")
                return {"status": 403}
            
            logger.info(f"Пользователь {user_id} подписался на канал чата {chat_id}")
        elif channel.startswith("user:"):
            # Каналы пользователей (user:UUID) доступны только самому пользователю
            channel_user_id = channel.split(":", 1)[1]
            
            if user_id != channel_user_id:
                logger.warning(f"Пользователь {user_id} пытается подписаться на чужой канал {channel}")
                return {"status": 403}
            
            logger.info(f"Пользователь {user_id} подписался на свой персональный канал")
        else:
            # Другие каналы запрещены
            logger.warning(f"Попытка подписки на неизвестный канал: {channel}")
            return {"status": 403}
        
        # Разрешаем подписку
        return {"result": {}}
    
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса на подписку: {str(e)}", exc_info=True)
        return {"status": 500}


@router.post("/publish", summary="Публикация сообщения в канал Centrifugo")
@async_time_it
async def publish_message(
    channel: str = Query(..., description="Канал Centrifugo для публикации"),
    data: Dict[str, Any] = Body(..., description="Данные для публикации"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Публикует сообщение в канал Centrifugo
    
    Args:
        channel: Канал в формате "chat:chat_id" или "user:user_id"
        data: Данные для публикации (текст сообщения, тип и т.д.)
        db: Сессия БД (внедряется через Depends)
        current_user: Текущий пользователь (внедряется через Depends)
        
    Returns:
        Результат публикации в Centrifugo
        
    Raises:
        HTTPException: Если доступ запрещен или произошла ошибка
    """
    try:
        # Проверяем формат канала
        if not channel or ":" not in channel:
            logger.warning(f"Некорректный формат канала: {channel}")
            raise HTTPException(
                status_code=400, 
                detail="Некорректный формат канала. Ожидается 'chat:id' или 'user:id'"
            )
        
        channel_type, channel_id = channel.split(":", 1)
        
        # Проверяем права доступа к каналу, если это канал чата
        if channel_type == "chat":
            has_access = await check_chat_access(db, current_user.id, channel_id)
            if not has_access:
                logger.warning(f"Отказано в доступе к каналу {channel} для пользователя {current_user.id}")
                raise HTTPException(
                    status_code=403, 
                    detail="У вас нет доступа к этому чату"
                )
        
        # Подготавливаем данные для публикации
        if isinstance(data, dict) and "sender_id" not in data:
            data["sender_id"] = current_user.id
            data["sender_name"] = current_user.name
        
        # Публикуем сообщение
        logger.info(f"Публикация сообщения в канал {channel}")
        result = await centrifugo_client.publish(channel=channel, data=data)
        
        # Если это текстовое сообщение чата, также сохраняем его в БД
        if (channel_type == "chat" and 
            isinstance(data, dict) and 
            data.get("type") in ["message", None] and
            "text" in data):
            
            # Извлекаем необходимые данные
            chat_id = channel_id
            text = data.get("text", "")
            client_message_id = data.get("client_message_id")
            attachments = data.get("attachments", [])
            
            # Сохраняем сообщение в БД
            message_id = await save_message_to_db(
                db=db,
                chat_id=chat_id,
                sender_id=current_user.id,
                text=text,
                client_message_id=client_message_id,
                attachments=attachments
            )
            
            if message_id:
                logger.info(f"Сообщение сохранено в БД, id={message_id}")
                # Добавляем ID сообщения в результат
                if isinstance(result, dict) and "result" in result:
                    result["message_id"] = message_id
        
        return result
    
    except HTTPException:
        # Пробрасываем HTTP-исключения дальше
        raise
    except Exception as e:
        logger.error(f"Ошибка при публикации сообщения: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Ошибка при публикации сообщения: {str(e)}"
        )


@router.post("/token", summary="Генерация токена для подключения к Centrifugo")
@async_time_it
async def generate_token(
    current_user: User = Depends(get_current_user)
):
    """
    Генерирует JWT токен для подключения к Centrifugo
    
    Клиенты должны запросить этот токен перед подключением к Centrifugo
    """
    try:
        token = centrifugo_client.generate_connection_token(
            user_id=str(current_user.id),
            user_name=current_user.name
        )
        return TokenResponse(token=token)
    except Exception as e:
        logger.error(f"Ошибка при генерации токена Centrifugo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при генерации токена: {str(e)}"
        )


@router.get("/presence/{chat_id}")
async def get_chat_presence(
    chat_id: int,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Получение списка активных пользователей в чате.
    """
    # Проверяем, имеет ли пользователь доступ к чату
    is_member = await is_user_in_chat(db, current_user.id, chat_id)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет доступа к этому чату"
        )
    
    try:
        # Получаем имя канала для чата
        channel = centrifugo_client.get_chat_channel_name(chat_id)
        
        # Запрашиваем данные о присутствии из Centrifugo
        presence_data = await centrifugo_client.presence(channel)
        
        if presence_data.get("status") == "error":
            logger.error(f"Ошибка при получении presence из Centrifugo: {presence_data}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось получить данные о присутствии"
            )
        
        return presence_data
    
    except Exception as e:
        logger.error(f"Ошибка при получении данных о присутствии: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось получить данные о присутствии: {str(e)}"
        )


@router.get("/token", summary="Получение токена для подключения к Centrifugo")
async def get_centrifugo_token(current_user: User = Depends(get_current_user)):
    """
    Генерирует токен для подключения к Centrifugo
    
    Args:
        current_user: Текущий пользователь
        
    Returns:
        Токен для подключения к Centrifugo
    """
    try:
        # Генерируем токен для пользователя
        token = centrifugo_client.generate_connection_token(
            user_id=current_user.id,
            user_name=current_user.name
        )
        
        return {"token": token}
    
    except Exception as e:
        logger.error(f"Ошибка при генерации токена Centrifugo: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Ошибка при генерации токена: {str(e)}"
        )


@router.get("/presence/{channel}", summary="Проверка присутствия пользователей в канале")
@async_time_it
async def check_presence(
    channel: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Проверяет, какие пользователи сейчас подключены к указанному каналу
    
    Args:
        channel: Канал в формате "chat:chat_id"
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Список подключенных пользователей
    """
    try:
        # Проверяем формат канала
        if not channel.startswith("chat:"):
            raise HTTPException(
                status_code=400, 
                detail="Некорректный формат канала. Ожидается 'chat:id'"
            )
        
        chat_id = channel.replace("chat:", "")
        
        # Проверяем права доступа к каналу
        has_access = await check_chat_access(db, current_user.id, chat_id)
        if not has_access:
            raise HTTPException(
                status_code=403, 
                detail="У вас нет доступа к этому чату"
            )
        
        # Запрашиваем данные о присутствии у Centrifugo
        presence_data = await centrifugo_client.presence(channel)
        
        return presence_data
    
    except HTTPException:
        # Пробрасываем HTTP-исключения дальше
        raise
    except Exception as e:
        logger.error(f"Ошибка при проверке присутствия: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Ошибка при проверке присутствия: {str(e)}"
        ) 