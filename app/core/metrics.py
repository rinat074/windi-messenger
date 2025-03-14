"""
Модуль для сбора и экспорта метрик приложения

Этот модуль предоставляет функции для сбора метрик производительности,
использования ресурсов и бизнес-метрик приложения.
"""
import time
import logging
import functools
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, push_to_gateway

# Настройка логирования
logger = logging.getLogger(__name__)

# Создаем реестр метрик
registry = CollectorRegistry()

# Метрики HTTP запросов
http_requests_total = Counter(
    'http_requests_total', 
    'Общее количество HTTP запросов',
    ['method', 'endpoint', 'status'],
    registry=registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'Длительность HTTP запросов в секундах',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')),
    registry=registry
)

# Метрики WebSocket
ws_connections_active = Gauge(
    'ws_connections_active',
    'Количество активных WebSocket соединений',
    ['channel_type'],
    registry=registry
)

ws_messages_total = Counter(
    'ws_messages_total',
    'Общее количество WebSocket сообщений',
    ['direction', 'message_type'],
    registry=registry
)

# Метрики Centrifugo
centrifugo_publish_total = Counter(
    'centrifugo_publish_total',
    'Общее количество публикаций в Centrifugo',
    ['channel_type', 'status'],
    registry=registry
)

centrifugo_publish_duration_seconds = Histogram(
    'centrifugo_publish_duration_seconds',
    'Длительность публикации в Centrifugo в секундах',
    ['channel_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, float('inf')),
    registry=registry
)

# Метрики базы данных
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Длительность запросов к базе данных в секундах',
    ['operation', 'table'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, float('inf')),
    registry=registry
)

db_errors_total = Counter(
    'db_errors_total',
    'Общее количество ошибок базы данных',
    ['operation', 'error_type'],
    registry=registry
)

# Бизнес-метрики
messages_sent_total = Counter(
    'messages_sent_total',
    'Общее количество отправленных сообщений',
    ['chat_type'],
    registry=registry
)

active_users_gauge = Gauge(
    'active_users',
    'Количество активных пользователей',
    registry=registry
)


async def metrics_middleware(request: Request, call_next) -> Response:
    """
    Middleware для сбора метрик HTTP запросов
    
    Args:
        request: Объект запроса FastAPI
        call_next: Следующая функция в цепочке middleware
        
    Returns:
        Response: Ответ FastAPI
    """
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # Получаем путь запроса без параметров запроса
        path = request.url.path
        
        # Для API эндпоинтов с динамическими параметрами (например, /api/v1/users/{id})
        # заменяем конкретные значения на {id} для группировки метрик
        if '/api/v1/' in path:
            parts = path.split('/')
            for i, part in enumerate(parts):
                # Если часть пути похожа на UUID или число, заменяем на {id}
                if (i > 0 and 
                    (part.isdigit() or 
                     (len(part) > 8 and '-' in part))):
                    parts[i] = '{id}'
            path = '/'.join(parts)
        
        # Записываем метрики
        http_requests_total.labels(
            method=request.method,
            endpoint=path,
            status=response.status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=path
        ).observe(time.time() - start_time)
        
        return response
    except Exception as e:
        # В случае ошибки также записываем метрики
        logger.error(f"Ошибка при обработке запроса: {str(e)}")
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=500
        ).inc()
        
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(time.time() - start_time)
        
        raise


def track_db_query(operation: str, table: str) -> Callable:
    """
    Декоратор для отслеживания запросов к базе данных
    
    Args:
        operation: Тип операции (select, insert, update, delete)
        table: Имя таблицы
        
    Returns:
        Callable: Декорированная функция
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # Записываем метрику длительности запроса
                db_query_duration_seconds.labels(
                    operation=operation,
                    table=table
                ).observe(time.time() - start_time)
                
                return result
            except Exception as e:
                # В случае ошибки записываем метрику ошибки
                error_type = type(e).__name__
                db_errors_total.labels(
                    operation=operation,
                    error_type=error_type
                ).inc()
                
                # Записываем метрику длительности запроса
                db_query_duration_seconds.labels(
                    operation=operation,
                    table=table
                ).observe(time.time() - start_time)
                
                raise
        
        return wrapper
    
    return decorator


def track_centrifugo_publish(channel: str, status: str = "success") -> None:
    """
    Отслеживание публикации в Centrifugo
    
    Args:
        channel: Канал Centrifugo
        status: Статус публикации (success/error)
    """
    # Определяем тип канала
    channel_type = "unknown"
    if channel.startswith("chat:"):
        channel_type = "chat"
    elif channel.startswith("user:"):
        channel_type = "user"
    elif channel.startswith("presence:"):
        channel_type = "presence"
    
    # Записываем метрику
    centrifugo_publish_total.labels(
        channel_type=channel_type,
        status=status
    ).inc()


def track_centrifugo_publish_time(channel: str, duration: float) -> None:
    """
    Отслеживание времени публикации в Centrifugo
    
    Args:
        channel: Канал Centrifugo
        duration: Длительность публикации в секундах
    """
    # Определяем тип канала
    channel_type = "unknown"
    if channel.startswith("chat:"):
        channel_type = "chat"
    elif channel.startswith("user:"):
        channel_type = "user"
    elif channel.startswith("presence:"):
        channel_type = "presence"
    
    # Записываем метрику
    centrifugo_publish_duration_seconds.labels(
        channel_type=channel_type
    ).observe(duration)


def track_websocket_message(direction: str, message_type: str) -> None:
    """
    Отслеживание WebSocket сообщений
    
    Args:
        direction: Направление сообщения (incoming/outgoing)
        message_type: Тип сообщения (message, typing, read, etc.)
    """
    ws_messages_total.labels(
        direction=direction,
        message_type=message_type
    ).inc()


def track_message_sent(chat_type: str = "private") -> None:
    """
    Отслеживание отправленных сообщений
    
    Args:
        chat_type: Тип чата (private/group)
    """
    messages_sent_total.labels(
        chat_type=chat_type
    ).inc()


def update_active_users(count: int) -> None:
    """
    Обновление количества активных пользователей
    
    Args:
        count: Количество активных пользователей
    """
    active_users_gauge.set(count)


def push_metrics(gateway_url: str, job: str) -> None:
    """
    Отправка метрик в Prometheus Push Gateway
    
    Args:
        gateway_url: URL Push Gateway
        job: Имя задачи
    """
    try:
        push_to_gateway(gateway_url, job=job, registry=registry)
        logger.info(f"Метрики успешно отправлены в Push Gateway: {gateway_url}")
    except Exception as e:
        logger.error(f"Ошибка при отправке метрик в Push Gateway: {str(e)}") 