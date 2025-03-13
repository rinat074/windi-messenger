"""
Утилиты для мониторинга производительности и профилирования кода
"""
import time
import functools
from typing import Any, Callable, TypeVar

from app.core.logging import get_logger

# Получение логгера
logger = get_logger("performance")

# Типизированные переменные для декораторов
F = TypeVar('F', bound=Callable[..., Any])
AsyncF = TypeVar('AsyncF', bound=Callable[..., Any])


def time_it(func: F) -> F:
    """
    Декоратор для измерения времени выполнения синхронных функций
    
    Args:
        func: Декорируемая функция
        
    Returns:
        Декорированная функция
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        
        logger.debug(f"Время выполнения {func.__name__}: {execution_time:.4f} секунд")
        return result
    
    return wrapper  # type: ignore


def async_time_it(func: AsyncF) -> AsyncF:
    """
    Декоратор для измерения времени выполнения асинхронных функций
    
    Args:
        func: Декорируемая асинхронная функция
        
    Returns:
        Декорированная асинхронная функция
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        
        logger.debug(f"Время выполнения {func.__name__}: {execution_time:.4f} секунд")
        return result
    
    return wrapper  # type: ignore


class PerformanceTracker:
    """
    Класс для отслеживания производительности в контексте
    
    Пример использования:
    ```python
    with PerformanceTracker("Загрузка пользователей"):
        users = await user_repo.get_all()
    ```
    """
    
    def __init__(self, operation_name: str):
        """
        Инициализация трекера производительности
        
        Args:
            operation_name: Название отслеживаемой операции
        """
        self.operation_name = operation_name
        self.start_time = 0.0
    
    def __enter__(self) -> "PerformanceTracker":
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        execution_time = time.time() - self.start_time
        logger.debug(f"Время выполнения '{self.operation_name}': {execution_time:.4f} секунд")


class AsyncPerformanceTracker:
    """
    Класс для отслеживания производительности в асинхронном контексте
    
    Пример использования:
    ```python
    async with AsyncPerformanceTracker("Загрузка пользователей"):
        users = await user_repo.get_all()
    ```
    """
    
    def __init__(self, operation_name: str):
        """
        Инициализация трекера производительности
        
        Args:
            operation_name: Название отслеживаемой операции
        """
        self.operation_name = operation_name
        self.start_time = 0.0
    
    async def __aenter__(self) -> "AsyncPerformanceTracker":
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        execution_time = time.time() - self.start_time
        logger.debug(f"Время выполнения '{self.operation_name}': {execution_time:.4f} секунд") 