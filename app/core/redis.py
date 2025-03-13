"""
Модуль для работы с Redis - кэширование, хранение состояния сессий, 
черный список токенов и другие возможности.
"""
import asyncio
import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

import redis.asyncio as redis
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging import get_logger

# Логгер для Redis-операций
logger = get_logger("redis")

# Префиксы для ключей в Redis
CACHE_PREFIX = "cache:"
TOKEN_BLACKLIST_PREFIX = "blacklist:"
RATE_LIMIT_PREFIX = "ratelimit:"
SESSION_PREFIX = "session:"
TYPING_PREFIX = "typing:"
ONLINE_PREFIX = "online:"


class RedisManager:
    """Менеджер для работы с Redis"""
    
    # Singleton instance
    _instance = None
    _redis = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisManager, cls).__new__(cls)
        return cls._instance
    
    async def initialize(self):
        """Инициализирует соединение с Redis"""
        if self._initialized:
            return
        
        try:
            self._redis = redis.Redis.from_url(
                settings.REDIS_URI,
                encoding="utf-8",
                decode_responses=True
            )
            # Проверка соединения
            await self._redis.ping()
            self._initialized = True
            logger.info("Соединение с Redis установлено")
        except Exception as e:
            logger.error(f"Ошибка подключения к Redis: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка подключения к Redis"
            )
    
    async def close(self):
        """Закрывает соединение с Redis"""
        if self._redis:
            await self._redis.close()
            self._initialized = False
            logger.info("Соединение с Redis закрыто")
    
    async def ensure_connection(self):
        """Проверяет, что соединение с Redis установлено"""
        if not self._initialized:
            await self.initialize()
    
    # Методы для кэширования
    
    async def cache_set(self, key: str, value: Any, expire_seconds: int = 300) -> bool:
        """Сохраняет значение в кэш"""
        await self.ensure_connection()
        
        # Добавляем префикс к ключу
        cache_key = f"{CACHE_PREFIX}{key}"
        
        # Сериализуем значение, если это не строка
        if not isinstance(value, str):
            value = json.dumps(value)
        
        try:
            await self._redis.set(cache_key, value, ex=expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении в кэш: {str(e)}")
            return False
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """Получает значение из кэша"""
        await self.ensure_connection()
        
        # Добавляем префикс к ключу
        cache_key = f"{CACHE_PREFIX}{key}"
        
        try:
            result = await self._redis.get(cache_key)
            if not result:
                return None
            
            # Пробуем десериализовать JSON, если не получается - возвращаем как есть
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return result
        except Exception as e:
            logger.error(f"Ошибка при получении из кэша: {str(e)}")
            return None
    
    async def cache_delete(self, key: str) -> bool:
        """Удаляет значение из кэша"""
        await self.ensure_connection()
        
        # Добавляем префикс к ключу
        cache_key = f"{CACHE_PREFIX}{key}"
        
        try:
            await self._redis.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении из кэша: {str(e)}")
            return False
    
    # Методы для управления черным списком токенов
    
    async def add_token_to_blacklist(self, token: str, expire_seconds: int) -> bool:
        """Добавляет токен в черный список"""
        await self.ensure_connection()
        
        blacklist_key = f"{TOKEN_BLACKLIST_PREFIX}{token}"
        
        try:
            await self._redis.set(blacklist_key, "1", ex=expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении токена в черный список: {str(e)}")
            return False
    
    async def is_token_blacklisted(self, token: str) -> bool:
        """Проверяет, находится ли токен в черном списке"""
        await self.ensure_connection()
        
        blacklist_key = f"{TOKEN_BLACKLIST_PREFIX}{token}"
        
        try:
            result = await self._redis.exists(blacklist_key)
            return bool(result)
        except Exception as e:
            logger.error(f"Ошибка при проверке токена в черном списке: {str(e)}")
            return False
    
    # Методы для ограничения количества запросов (rate limiting)
    
    async def increment_request_count(self, identifier: str, window_seconds: int = 60) -> int:
        """
        Увеличивает счетчик запросов для определенного идентификатора
        
        Args:
            identifier: Идентификатор (например, IP-адрес)
            window_seconds: Временное окно в секундах
            
        Returns:
            int: Текущее количество запросов
        """
        await self.ensure_connection()
        
        rate_key = f"{RATE_LIMIT_PREFIX}{identifier}"
        
        try:
            # Увеличиваем счетчик
            current = await self._redis.incr(rate_key)
            
            # Устанавливаем время жизни при первом запросе
            if current == 1:
                await self._redis.expire(rate_key, window_seconds)
            
            return current
        except Exception as e:
            logger.error(f"Ошибка при увеличении счетчика запросов: {str(e)}")
            return 0
    
    async def get_request_count(self, identifier: str) -> int:
        """Получает текущее количество запросов для идентификатора"""
        await self.ensure_connection()
        
        rate_key = f"{RATE_LIMIT_PREFIX}{identifier}"
        
        try:
            count = await self._redis.get(rate_key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"Ошибка при получении счетчика запросов: {str(e)}")
            return 0
    
    # Методы для отслеживания статуса печати
    
    async def set_typing_status(self, user_id: str, chat_id: str, expire_seconds: int = 10) -> bool:
        """Устанавливает статус печати для пользователя в чате"""
        await self.ensure_connection()
        
        typing_key = f"{TYPING_PREFIX}{chat_id}:{user_id}"
        
        try:
            await self._redis.set(typing_key, "1", ex=expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Ошибка при установке статуса печати: {str(e)}")
            return False
    
    async def clear_typing_status(self, user_id: str, chat_id: str) -> bool:
        """Сбрасывает статус печати для пользователя в чате"""
        await self.ensure_connection()
        
        typing_key = f"{TYPING_PREFIX}{chat_id}:{user_id}"
        
        try:
            await self._redis.delete(typing_key)
            return True
        except Exception as e:
            logger.error(f"Ошибка при сбросе статуса печати: {str(e)}")
            return False
    
    async def get_typing_users(self, chat_id: str) -> List[str]:
        """Получает список пользователей, печатающих в чате"""
        await self.ensure_connection()
        
        typing_pattern = f"{TYPING_PREFIX}{chat_id}:*"
        
        try:
            keys = await self._redis.keys(typing_pattern)
            users = [key.split(":")[-1] for key in keys]
            return users
        except Exception as e:
            logger.error(f"Ошибка при получении списка печатающих пользователей: {str(e)}")
            return []
    
    # Методы для отслеживания онлайн-статуса пользователей
    
    async def set_user_online(self, user_id: str, device_id: str = None, expire_seconds: int = 300) -> bool:
        """Устанавливает статус 'онлайн' для пользователя"""
        await self.ensure_connection()
        
        online_key = f"{ONLINE_PREFIX}{user_id}"
        
        try:
            if device_id:
                # Если указан device_id, добавляем его в Set
                await self._redis.sadd(online_key, device_id)
            else:
                # Иначе просто устанавливаем ключ
                await self._redis.set(online_key, "1")
            
            # Устанавливаем время жизни
            await self._redis.expire(online_key, expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Ошибка при установке статуса 'онлайн': {str(e)}")
            return False
    
    async def remove_user_online(self, user_id: str, device_id: str = None) -> bool:
        """Удаляет статус 'онлайн' для пользователя или устройства"""
        await self.ensure_connection()
        
        online_key = f"{ONLINE_PREFIX}{user_id}"
        
        try:
            if device_id:
                # Если указан device_id, удаляем его из Set
                await self._redis.srem(online_key, device_id)
                
                # Если устройств больше нет, удаляем ключ
                if not await self._redis.scard(online_key):
                    await self._redis.delete(online_key)
            else:
                # Иначе удаляем весь ключ
                await self._redis.delete(online_key)
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении статуса 'онлайн': {str(e)}")
            return False
    
    async def is_user_online(self, user_id: str) -> bool:
        """Проверяет, онлайн ли пользователь"""
        await self.ensure_connection()
        
        online_key = f"{ONLINE_PREFIX}{user_id}"
        
        try:
            return bool(await self._redis.exists(online_key))
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса 'онлайн': {str(e)}")
            return False
    
    async def get_online_users(self) -> List[str]:
        """Получает список онлайн-пользователей"""
        await self.ensure_connection()
        
        online_pattern = f"{ONLINE_PREFIX}*"
        
        try:
            keys = await self._redis.keys(online_pattern)
            users = [key.replace(ONLINE_PREFIX, "") for key in keys]
            return users
        except Exception as e:
            logger.error(f"Ошибка при получении списка онлайн-пользователей: {str(e)}")
            return []
    
    # Методы для публикации/подписки (pub/sub)
    
    async def publish(self, channel: str, message: Union[str, Dict]) -> bool:
        """Публикует сообщение в канал"""
        await self.ensure_connection()
        
        if not isinstance(message, str):
            message = json.dumps(message)
        
        try:
            await self._redis.publish(channel, message)
            return True
        except Exception as e:
            logger.error(f"Ошибка при публикации сообщения: {str(e)}")
            return False
    
    async def subscribe(self, channel: str):
        """
        Подписывается на канал и возвращает генератор сообщений
        
        Использование:
        ```
        async for message in redis_manager.subscribe("channel"):
            print(message)
        ```
        """
        await self.ensure_connection()
        
        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(channel)
            
            # Возвращаем асинхронный генератор сообщений
            async def message_generator():
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True)
                    if message:
                        data = message["data"]
                        try:
                            # Пытаемся распарсить JSON
                            yield json.loads(data)
                        except (json.JSONDecodeError, TypeError):
                            yield data
                    else:
                        await asyncio.sleep(0.01)
            
            return message_generator()
        except Exception as e:
            logger.error(f"Ошибка при подписке на канал: {str(e)}")
            raise
    
    # Методы для управления сессиями
    
    async def clean_inactive_sessions(self) -> int:
        """
        Очищает неактивные сессии старше определенного срока
        
        Returns:
            int: Количество удаленных сессий
        """
        await self.ensure_connection()
        
        try:
            # Получаем все ключи сессий
            session_pattern = f"{SESSION_PREFIX}*"
            session_keys = await self._redis.keys(session_pattern)
            
            if not session_keys:
                logger.info("Нет сессий для очистки")
                return 0
            
            # Вычисляем порог активности (в днях)
            cleanup_days = settings.SESSION_CLEANUP_DAYS
            logger.info(f"Очистка сессий старше {cleanup_days} дней")
            
            # Удаляем старые сессии
            removed_count = 0
            
            for key in session_keys:
                # Получаем данные сессии
                session_data = await self._redis.get(key)
                if not session_data:
                    continue
                
                try:
                    # Парсим данные сессии
                    session_info = json.loads(session_data)
                    last_active = session_info.get("last_active")
                    
                    # Если сессия старая, удаляем её
                    if last_active:
                        last_active_date = datetime.fromisoformat(last_active)
                        days_inactive = (datetime.now() - last_active_date).days
                        
                        if days_inactive > cleanup_days:
                            await self._redis.delete(key)
                            removed_count += 1
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    logger.warning(f"Ошибка при обработке сессии {key}: {str(e)}")
                    # Удаляем поврежденную сессию
                    await self._redis.delete(key)
                    removed_count += 1
            
            logger.info(f"Удалено {removed_count} неактивных сессий")
            return removed_count
        
        except Exception as e:
            logger.error(f"Ошибка при очистке неактивных сессий: {str(e)}")
            return 0


# Создание глобального экземпляра менеджера Redis
redis_manager = RedisManager() 