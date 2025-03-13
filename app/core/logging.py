import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Создание директории для логов, если ее нет
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Настройка форматтеров для логов
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
console_formatter = logging.Formatter(
    "%(levelname)s: [%(name)s] %(message)s (%(asctime)s)"
)

# Настройка обработчиков для логов
def setup_logging(log_level: str = "INFO") -> None:
    """
    Настройка логирования приложения
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Преобразование уровня логирования из строки
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Очистка обработчиков, если они уже существуют
    root_logger.handlers.clear()
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Обработчик для файла
    log_file = LOG_DIR / f"app_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Отдельный файл для ошибок
    error_file = LOG_DIR / f"errors_{datetime.now().strftime('%Y-%m-%d')}.log"
    error_handler = logging.FileHandler(error_file)
    error_handler.setFormatter(file_formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
    
    # Логирование начала настройки
    root_logger.info(f"Logging configured with level {log_level}")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware для логирования запросов и ответов
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Обработка запроса/ответа с логированием
        
        Args:
            request: Входящий запрос
            call_next: Следующий обработчик в цепочке
            
        Returns:
            Response: Ответ сервера
        """
        logger = logging.getLogger("api")
        
        # Генерируем уникальный ID для запроса
        request_id = f"{time.time():.0f}"
        
        # Логирование запроса
        await self._log_request(request, request_id, logger)
        
        start_time = time.time()
        
        try:
            # Вызов следующего обработчика
            response = await call_next(request)
            
            # Расчет времени обработки
            process_time = time.time() - start_time
            
            # Логирование ответа
            await self._log_response(response, request_id, process_time, logger)
            
            return response
        except Exception as e:
            # Логирование исключения
            process_time = time.time() - start_time
            logger.error(
                f"Request {request_id} failed after {process_time:.4f}s: {str(e)}",
                exc_info=True
            )
            raise
            
    async def _log_request(self, request: Request, request_id: str, logger: logging.Logger) -> None:
        """Логирование запроса"""
        # Собираем заголовки для логирования
        headers = {k.decode(): v.decode() for k, v in request.headers.raw}
        # Скрываем чувствительные данные
        if "authorization" in headers:
            headers["authorization"] = "Bearer *****"
        
        # Формируем информацию о запросе
        request_info = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "headers": headers,
            "client": request.client.host if request.client else None,
        }
        
        # Логируем информацию о запросе
        logger.info(f"Request {request_id}: {json.dumps(request_info)}")
    
    async def _log_response(self, response: Response, request_id: str, 
                           process_time: float, logger: logging.Logger) -> None:
        """Логирование ответа"""
        # Формируем информацию об ответе
        response_info = {
            "request_id": request_id,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "processing_time": f"{process_time:.4f}s",
        }
        
        # Уровень логирования зависит от статус-кода
        if response.status_code >= 500:
            logger.error(f"Response {request_id}: {json.dumps(response_info)}")
        elif response.status_code >= 400:
            logger.warning(f"Response {request_id}: {json.dumps(response_info)}")
        else:
            logger.info(f"Response {request_id}: {json.dumps(response_info)}")


# Настройка логгеров для различных модулей
def get_logger(name: str) -> logging.Logger:
    """
    Получение логгера для модуля
    
    Args:
        name: Имя модуля
        
    Returns:
        Logger: Настроенный логгер
    """
    return logging.getLogger(name) 