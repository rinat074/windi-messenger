"""
Модуль для управления аутентификацией, авторизацией и JWT-токенами
"""
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple

from fastapi import HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import redis_manager
from app.schemas.token import TokenData

# Создание логгера
logger = get_logger("auth")

# Схема OAuth2 для токенов
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/users/login")

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Функции для работы с паролями

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет соответствие пароля хешу"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Создает хеш пароля"""
    return pwd_context.hash(password)


# Функции для работы с JWT-токенами

def create_access_token(subject: Any, expires_delta: int = None) -> str:
    """
    Создает JWT-токен доступа
    
    Args:
        subject: Идентификатор пользователя
        expires_delta: Время действия токена в минутах
        
    Returns:
        str: Сгенерированный JWT-токен
    """
    if expires_delta is None:
        expires_delta = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    # Срок действия токена
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    
    # Данные токена
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": f"{datetime.utcnow().timestamp()}"  # Уникальный ID токена для отзыва
    }
    
    # Кодирование токена
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


async def decode_token(token: str) -> Tuple[bool, Optional[TokenData], Optional[str]]:
    """
    Декодирует и проверяет JWT-токен
    
    Args:
        token: JWT-токен для проверки
        
    Returns:
        Tuple[bool, Optional[TokenData], Optional[str]]: 
            - Успешность операции
            - Данные токена (если успешно)
            - Сообщение об ошибке (если неуспешно)
    """
    try:
        # Проверка токена в черном списке
        if await redis_manager.is_token_blacklisted(token):
            return False, None, "Токен отозван или находится в черном списке"
        
        # Декодирование токена
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        # Извлечение данных
        user_id = payload.get("sub")
        if user_id is None:
            return False, None, "Некорректный токен - отсутствует идентификатор пользователя"
        
        # Проверка срока действия
        expiration = payload.get("exp")
        if expiration is None:
            return False, None, "Некорректный токен - отсутствует срок действия"
        
        if datetime.fromtimestamp(expiration) < datetime.utcnow():
            return False, None, "Срок действия токена истек"
        
        # Создание объекта с данными токена
        token_data = TokenData(user_id=user_id)
        return True, token_data, None
    
    except JWTError as e:
        logger.error(f"Ошибка при декодировании JWT-токена: {str(e)}")
        return False, None, f"Невозможно декодировать токен: {str(e)}"
    
    except Exception as e:
        logger.error(f"Необработанное исключение при декодировании токена: {str(e)}", exc_info=True)
        return False, None, f"Внутренняя ошибка при декодировании токена: {str(e)}"


async def revoke_token(token: str) -> bool:
    """
    Отзывает JWT-токен, добавляя его в черный список
    
    Args:
        token: JWT-токен для отзыва
        
    Returns:
        bool: Успешность операции
    """
    try:
        # Декодирование токена для получения срока действия
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        # Извлечение срока действия
        expiration = payload.get("exp")
        if expiration is None:
            logger.error("Невозможно отозвать токен - отсутствует срок действия")
            return False
        
        # Вычисление оставшегося времени действия токена в секундах
        now = datetime.utcnow().timestamp()
        ttl = max(0, int(expiration - now))
        
        # Добавление токена в черный список с тем же сроком действия
        result = await redis_manager.add_token_to_blacklist(token, ttl)
        
        if result:
            logger.info(f"Токен пользователя {payload.get('sub')} успешно отозван")
        else:
            logger.error("Ошибка при добавлении токена в черный список")
            
        return result
    
    except JWTError as e:
        logger.error(f"Ошибка при отзыве токена: {str(e)}")
        return False
    
    except Exception as e:
        logger.error(f"Необработанное исключение при отзыве токена: {str(e)}", exc_info=True)
        return False


# Защита от брутфорса

async def check_login_attempts(ip_address: str) -> bool:
    """
    Проверяет, не превышено ли количество попыток входа с этого IP-адреса
    
    Args:
        ip_address: IP-адрес пользователя
        
    Returns:
        bool: True, если превышено, False в противном случае
    """
    identifier = f"login:{ip_address}"
    
    # Получаем текущее количество попыток
    count = await redis_manager.get_request_count(identifier)
    
    # Проверяем, не превышен ли лимит
    return count >= settings.MAX_LOGIN_ATTEMPTS


async def register_failed_login(ip_address: str) -> int:
    """
    Регистрирует неудачную попытку входа
    
    Args:
        ip_address: IP-адрес пользователя
        
    Returns:
        int: Текущее количество попыток
    """
    identifier = f"login:{ip_address}"
    
    # Увеличиваем счетчик попыток
    count = await redis_manager.increment_request_count(
        identifier, 
        settings.LOGIN_ATTEMPT_TIMEOUT
    )
    
    if count >= settings.MAX_LOGIN_ATTEMPTS:
        logger.warning(f"Превышено количество попыток входа с IP: {ip_address}")
    
    return count


async def reset_login_attempts(ip_address: str) -> bool:
    """
    Сбрасывает счетчик неудачных попыток входа
    
    Args:
        ip_address: IP-адрес пользователя
        
    Returns:
        bool: Успешность операции
    """
    identifier = f"login:{ip_address}"
    return await redis_manager.cache_delete(identifier)


# Middleware для ограничения числа запросов

async def rate_limit_middleware(request: Request, call_next: Any):
    """
    Middleware для ограничения числа запросов (rate limiting)
    
    Args:
        request: HTTP-запрос
        call_next: Следующая функция в цепочке обработки
    """
    # Получаем IP-адрес клиента
    ip = request.client.host
    
    # Путь запроса
    path = request.url.path
    
    # Выбор лимита в зависимости от запроса
    if path.endswith("/login"):
        limit = settings.RATE_LIMIT_LOGIN
    else:
        limit = settings.RATE_LIMIT_DEFAULT
    
    # Формируем идентификатор запроса
    identifier = f"{ip}:{path}"
    
    # Увеличиваем счетчик запросов
    count = await redis_manager.increment_request_count(identifier)
    
    # Если лимит превышен, возвращаем ошибку
    if count > limit:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests"
        )
    
    # Добавляем заголовки с информацией о лимите
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
    
    return response 