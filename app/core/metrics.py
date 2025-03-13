"""
Модуль для сбора и экспорта метрик Prometheus
"""
import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Gauge, Histogram, Summary
from prometheus_client.openmetrics.exposition import generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

# Логгер для модуля метрик
logger = get_logger("metrics")

# Метрики HTTP-запросов
REQUEST_COUNT = Counter(
    "app_request_count", 
    "Количество HTTP-запросов",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "app_request_latency_seconds", 
    "Время обработки HTTP-запросов",
    ["method", "endpoint"]
)

# Метрики WebSocket
WEBSOCKET_CONNECTIONS = Gauge(
    "app_websocket_connections", 
    "Количество активных WebSocket-соединений"
)

WEBSOCKET_MESSAGES = Counter(
    "app_websocket_messages", 
    "Количество сообщений через WebSocket",
    ["direction", "type"]
)

# Метрики аутентификации
LOGIN_SUCCESS = Counter(
    "app_login_success", 
    "Количество успешных входов в систему"
)

LOGIN_FAILURE = Counter(
    "app_login_failure", 
    "Количество неудачных попыток входа"
)

# Метрики сессий
ACTIVE_SESSIONS = Gauge(
    "app_active_sessions", 
    "Количество активных сессий"
)

# Метрики сообщений
MESSAGE_COUNT = Counter(
    "app_message_count", 
    "Количество отправленных сообщений"
)

# Метрики системных ресурсов
MEMORY_USAGE = Gauge(
    "app_memory_usage_bytes", 
    "Использование памяти приложением (байты)"
)

CPU_USAGE = Gauge(
    "app_cpu_usage_percent", 
    "Использование CPU приложением (%)"
)

DB_QUERY_TIME = Summary(
    "app_db_query_time_seconds", 
    "Время выполнения запросов к БД",
    ["query_type"]
)

REDIS_OPERATION_TIME = Summary(
    "app_redis_operation_time_seconds", 
    "Время выполнения операций с Redis",
    ["operation_type"]
)

# Метрики для кэширования
CACHE_HIT = Counter(
    "app_cache_hit", 
    "Количество успешных обращений к кэшу",
    ["cache_type"]
)

CACHE_MISS = Counter(
    "app_cache_miss", 
    "Количество промахов кэша",
    ["cache_type"]
)


# Middleware для сбора метрик HTTP-запросов
class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware для сбора метрик HTTP-запросов
    
    Собирает информацию о количестве запросов и времени их обработки
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Не собираем метрики для запросов к эндпоинту метрик
        if request.url.path == settings.METRICS_PATH:
            return await call_next(request)
        
        # Фиксируем начало выполнения запроса
        start_time = time.time()
        
        # Выполняем запрос
        try:
            response = await call_next(request)
            
            # Формируем метки для метрик
            method = request.method
            endpoint = request.url.path
            status = response.status_code
            
            # Увеличиваем счетчик запросов
            REQUEST_COUNT.labels(
                method=method, 
                endpoint=endpoint, 
                status=status
            ).inc()
            
            # Фиксируем время выполнения запроса
            duration = time.time() - start_time
            REQUEST_LATENCY.labels(
                method=method, 
                endpoint=endpoint
            ).observe(duration)
            
            return response
        
        except Exception as e:
            # В случае ошибки также фиксируем метрики
            method = request.method
            endpoint = request.url.path
            status = 500  # Internal Server Error
            
            # Увеличиваем счетчик запросов
            REQUEST_COUNT.labels(
                method=method, 
                endpoint=endpoint, 
                status=status
            ).inc()
            
            # Фиксируем время выполнения запроса
            duration = time.time() - start_time
            REQUEST_LATENCY.labels(
                method=method, 
                endpoint=endpoint
            ).observe(duration)
            
            # Передаем исключение дальше
            raise


# Функция для настройки метрик в приложении
def setup_metrics(app: FastAPI) -> None:
    """
    Настраивает сбор метрик для FastAPI-приложения
    
    Args:
        app: FastAPI-приложение
    """
    # Добавляем middleware для сбора метрик
    app.add_middleware(PrometheusMiddleware)
    
    # Добавляем маршрут для экспорта метрик в формате Prometheus
    @app.get(settings.METRICS_PATH, include_in_schema=False)
    async def metrics():
        return Response(
            content=generate_latest(),
            media_type="text/plain"
        )
    
    logger.info("Метрики Prometheus настроены")


# Функции-помощники для сбора метрик

def track_login_success() -> None:
    """Увеличивает счетчик успешных входов в систему"""
    LOGIN_SUCCESS.inc()


def track_login_failure() -> None:
    """Увеличивает счетчик неудачных попыток входа"""
    LOGIN_FAILURE.inc()


def set_active_sessions(count: int) -> None:
    """Устанавливает количество активных сессий"""
    ACTIVE_SESSIONS.set(count)


def track_message_sent() -> None:
    """Увеличивает счетчик отправленных сообщений"""
    MESSAGE_COUNT.inc()


def track_websocket_message(direction: str, message_type: str) -> None:
    """
    Увеличивает счетчик сообщений через WebSocket
    
    Args:
        direction: Направление сообщения ('sent' или 'received')
        message_type: Тип сообщения (например, 'message', 'typing', 'read_receipt')
    """
    WEBSOCKET_MESSAGES.labels(
        direction=direction,
        type=message_type
    ).inc()


def set_websocket_connections(count: int) -> None:
    """
    Устанавливает количество активных WebSocket-соединений
    
    Args:
        count: Количество соединений
    """
    WEBSOCKET_CONNECTIONS.set(count)


def track_db_query_time(query_type: str, duration: float) -> None:
    """
    Фиксирует время выполнения запроса к БД
    
    Args:
        query_type: Тип запроса (например, 'select', 'insert', 'update', 'delete')
        duration: Время выполнения в секундах
    """
    DB_QUERY_TIME.labels(query_type=query_type).observe(duration)


def track_redis_operation_time(operation_type: str, duration: float) -> None:
    """
    Фиксирует время выполнения операции с Redis
    
    Args:
        operation_type: Тип операции (например, 'get', 'set', 'del', 'pub', 'sub')
        duration: Время выполнения в секундах
    """
    REDIS_OPERATION_TIME.labels(operation_type=operation_type).observe(duration)


def track_cache_hit(cache_type: str) -> None:
    """
    Увеличивает счетчик успешных обращений к кэшу
    
    Args:
        cache_type: Тип кэша (например, 'redis', 'memory')
    """
    CACHE_HIT.labels(cache_type=cache_type).inc()


def track_cache_miss(cache_type: str) -> None:
    """
    Увеличивает счетчик промахов кэша
    
    Args:
        cache_type: Тип кэша (например, 'redis', 'memory')
    """
    CACHE_MISS.labels(cache_type=cache_type).inc()


def set_system_metrics(memory_bytes: int, cpu_percent: float) -> None:
    """
    Устанавливает метрики системных ресурсов
    
    Args:
        memory_bytes: Использование памяти в байтах
        cpu_percent: Использование CPU в процентах
    """
    MEMORY_USAGE.set(memory_bytes)
    CPU_USAGE.set(cpu_percent) 