import time
import uuid
import logging
from typing import Dict, Any, Optional, List, Union

import httpx
from jose import jwt

from app.core.config import settings
from app.schemas.message import MessageCreate, MessageOut

logger = logging.getLogger(__name__)

class CentrifugoClient:
    """Клиент для взаимодействия с Centrifugo API."""
    
    def __init__(self):
        self.api_url = f"{settings.CENTRIFUGO_URL}/api"
        self.api_key = settings.CENTRIFUGO_API_KEY
        self.token_secret = settings.CENTRIFUGO_TOKEN_SECRET
        self.token_expire = settings.CENTRIFUGO_TOKEN_EXPIRE_SECONDS
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"apikey {self.api_key}"
        }
    
    async def publish(self, channel: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Публикация сообщения в канал Centrifugo."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "method": "publish",
                    "params": {
                        "channel": channel,
                        "data": data
                    }
                }
                
                response = await client.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=5.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Ошибка при публикации в Centrifugo: {response.text}")
                    return {"status": "error", "error": response.text}
                
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка при публикации в Centrifugo: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def broadcast(self, channels: List[str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Публикация сообщения в несколько каналов Centrifugo."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "method": "broadcast",
                    "params": {
                        "channels": channels,
                        "data": data
                    }
                }
                
                response = await client.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=5.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Ошибка при трансляции в Centrifugo: {response.text}")
                    return {"status": "error", "error": response.text}
                
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка при трансляции в Centrifugo: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def presence(self, channel: str) -> Dict[str, Any]:
        """Получение списка присутствующих в канале пользователей."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "method": "presence",
                    "params": {
                        "channel": channel
                    }
                }
                
                response = await client.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=5.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Ошибка при получении presence из Centrifugo: {response.text}")
                    return {"status": "error", "error": response.text}
                
                result = response.json()
                return result.get("result", {})
        except Exception as e:
            logger.error(f"Ошибка при получении presence из Centrifugo: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def history(self, channel: str, limit: int = 100) -> Dict[str, Any]:
        """Получение истории сообщений из канала."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "method": "history",
                    "params": {
                        "channel": channel,
                        "limit": limit
                    }
                }
                
                response = await client.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=5.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Ошибка при получении истории из Centrifugo: {response.text}")
                    return {"status": "error", "error": response.text}
                
                result = response.json()
                return result.get("result", {})
        except Exception as e:
            logger.error(f"Ошибка при получении истории из Centrifugo: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def generate_connection_token(self, user_id: str, user_name: Optional[str] = None, 
                                 expires_at: Optional[int] = None) -> str:
        """Генерация JWT токена для подключения к Centrifugo."""
        if expires_at is None:
            expires_at = int(time.time()) + self.token_expire
        
        claims = {
            "sub": str(user_id),
            "exp": expires_at,
        }
        
        if user_name:
            claims["info"] = {"name": user_name}
        
        return jwt.encode(claims, self.token_secret, algorithm="HS256")
    
    def generate_channel_token(self, user_id: str, channel: str, 
                              expires_at: Optional[int] = None) -> str:
        """Генерация JWT токена для подписки на канал Centrifugo."""
        if expires_at is None:
            expires_at = int(time.time()) + self.token_expire
        
        claims = {
            "sub": str(user_id),
            "channel": channel,
            "exp": expires_at,
        }
        
        return jwt.encode(claims, self.token_secret, algorithm="HS256")

    def get_chat_channel_name(self, chat_id: int) -> str:
        """Получение имени канала для чата."""
        return f"chat:{chat_id}"
    
    def get_user_channel_name(self, user_id: int) -> str:
        """Получение имени канала для приватных уведомлений пользователя."""
        return f"user:{user_id}"
    
    def format_message_for_centrifugo(self, message: Union[MessageCreate, MessageOut]) -> Dict[str, Any]:
        """Форматирует сообщение для отправки через Centrifugo."""
        message_dict = message.dict() if hasattr(message, "dict") else dict(message)
        
        # Добавляем технические поля для Centrifugo
        message_dict["id"] = message_dict.get("id", str(uuid.uuid4()))
        message_dict["timestamp"] = message_dict.get("created_at", int(time.time()))
        
        return message_dict

centrifugo_client = CentrifugoClient() 