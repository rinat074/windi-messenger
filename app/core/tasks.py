"""
Модуль для асинхронного выполнения задач в фоновом режиме
Реализует простой планировщик задач на основе asyncio
"""
import asyncio
import functools
import inspect
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from app.core.logging import get_logger

# Логгер для модуля задач
logger = get_logger("tasks")


class TaskStatus(str, Enum):
    """Статусы задач"""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskInfo:
    """Информация о задаче"""
    
    def __init__(
        self,
        task_id: str,
        func: Callable,
        args: tuple,
        kwargs: dict,
        scheduled_at: datetime,
        periodic: bool = False,
        interval: Optional[int] = None,
        max_retries: int = 0,
        timeout: Optional[float] = None,
        description: Optional[str] = None
    ):
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.scheduled_at = scheduled_at
        self.periodic = periodic
        self.interval = interval
        self.max_retries = max_retries
        self.retry_count = 0
        self.timeout = timeout
        self.description = description or f"Task {func.__name__}"
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self._task = None  # asyncio.Task instance
    
    @property
    def is_due(self) -> bool:
        """Проверяет, пора ли выполнять задачу"""
        return datetime.now() >= self.scheduled_at
    
    @property
    def can_retry(self) -> bool:
        """Проверяет, можно ли повторить задачу"""
        return self.retry_count < self.max_retries
    
    def schedule_next_run(self) -> None:
        """Планирует следующее выполнение периодической задачи"""
        if self.periodic and self.interval:
            self.scheduled_at = datetime.now() + timedelta(seconds=self.interval)
            self.status = TaskStatus.PENDING
            self.retry_count = 0


class TaskQueue:
    """
    Менеджер очереди асинхронных задач
    
    Реализует функционал для добавления, выполнения и отслеживания задач
    """
    
    # Singleton instance
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskQueue, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Инициализация менеджера задач"""
        if self._initialized:
            return
        
        # Задачи по идентификаторам
        self._tasks: Dict[str, TaskInfo] = {}
        
        # Множество задач, ожидающих выполнения
        self._pending_tasks: Set[str] = set()
        
        # Флаг работы планировщика
        self._running = False
        
        # Задача планировщика
        self._scheduler_task = None
        
        # Очереди задач по приоритетам (low, normal, high)
        self._queues = {
            'high': asyncio.PriorityQueue(),
            'normal': asyncio.PriorityQueue(),
            'low': asyncio.PriorityQueue()
        }
        
        # Список воркеров (asyncio.Task)
        self._workers: List[asyncio.Task] = []
        
        # Количество воркеров по умолчанию
        self._default_worker_count = 3
        
        # Флаг инициализации
        self._initialized = True
        
        logger.info("TaskQueue инициализирован")
    
    async def start(self, worker_count: Optional[int] = None) -> None:
        """
        Запускает планировщик задач и воркеры
        
        Args:
            worker_count: Количество воркеров, по умолчанию 3
        """
        if self._running:
            logger.warning("TaskQueue уже запущен")
            return
        
        if worker_count is None:
            worker_count = self._default_worker_count
        
        self._running = True
        
        # Запускаем планировщик
        self._scheduler_task = asyncio.create_task(
            self._scheduler_loop(),
            name="task_scheduler"
        )
        
        # Запускаем воркеры
        for i in range(worker_count):
            worker = asyncio.create_task(
                self._worker_loop(f"worker-{i}"),
                name=f"task_worker_{i}"
            )
            self._workers.append(worker)
        
        logger.info(f"TaskQueue запущен с {worker_count} воркерами")
    
    async def stop(self) -> None:
        """Останавливает планировщик задач и воркеры"""
        if not self._running:
            logger.warning("TaskQueue уже остановлен")
            return
        
        self._running = False
        
        # Отменяем планировщик
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Отменяем воркеры
        for worker in self._workers:
            worker.cancel()
        
        try:
            await asyncio.gather(*self._workers, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        
        self._workers = []
        logger.info("TaskQueue остановлен")
    
    async def _scheduler_loop(self) -> None:
        """Цикл планировщика задач"""
        logger.info("Планировщик задач запущен")
        
        while self._running:
            try:
                # Проверяем все задачи, которые пора выполнить
                current_time = datetime.now()
                tasks_to_run = []
                
                for task_id in list(self._pending_tasks):
                    task_info = self._tasks.get(task_id)
                    if not task_info:
                        self._pending_tasks.remove(task_id)
                        continue
                    
                    if task_info.is_due:
                        tasks_to_run.append(task_info)
                        self._pending_tasks.remove(task_id)
                
                # Добавляем задачи в соответствующие очереди
                for task_info in tasks_to_run:
                    priority = task_info.kwargs.pop('priority', 'normal')
                    if priority not in self._queues:
                        priority = 'normal'
                    
                    # Приоритет в очереди (меньшее значение = выше приоритет)
                    queue_priority = time.time()
                    
                    await self._queues[priority].put((queue_priority, task_info.task_id))
                    task_info.status = TaskStatus.PENDING
                
                await asyncio.sleep(0.1)  # Небольшая пауза для снижения нагрузки
            
            except asyncio.CancelledError:
                logger.info("Планировщик задач остановлен")
                break
            
            except Exception as e:
                logger.error(f"Ошибка в планировщике задач: {str(e)}", exc_info=True)
                await asyncio.sleep(1)  # Пауза перед повторной попыткой
    
    async def _worker_loop(self, worker_name: str) -> None:
        """
        Цикл обработки задач воркером
        
        Args:
            worker_name: Имя воркера для логирования
        """
        logger.info(f"Воркер {worker_name} запущен")
        
        while self._running:
            task_id = None
            task_info = None
            
            try:
                # Проверяем очереди по приоритету
                for queue_name in ['high', 'normal', 'low']:
                    queue = self._queues[queue_name]
                    
                    if not queue.empty():
                        _, task_id = await queue.get()
                        task_info = self._tasks.get(task_id)
                        
                        if task_info:
                            break
                        else:
                            queue.task_done()
                
                # Если ни в одной очереди нет задач, ждем
                if not task_info:
                    await asyncio.sleep(0.1)
                    continue
                
                # Выполняем задачу
                await self._execute_task(task_info)
                
                # Помечаем задачу в очереди как выполненную
                queue.task_done()
            
            except asyncio.CancelledError:
                logger.info(f"Воркер {worker_name} остановлен")
                break
            
            except Exception as e:
                logger.error(f"Ошибка в воркере {worker_name}: {str(e)}", exc_info=True)
                
                # Если была задача, помечаем её как проваленную
                if task_info:
                    task_info.status = TaskStatus.FAILED
                    task_info.error = str(e)
                
                # Пауза перед повторной попыткой
                await asyncio.sleep(1)
    
    async def _execute_task(self, task_info: TaskInfo) -> None:
        """
        Выполняет задачу
        
        Args:
            task_info: Информация о задаче
        """
        task_info.status = TaskStatus.RUNNING
        task_info.started_at = datetime.now()
        task_info._task = asyncio.current_task()
        
        logger.debug(f"Выполнение задачи {task_info.task_id} ({task_info.description})")
        
        try:
            # Применяем таймаут, если установлен
            if task_info.timeout:
                task_result = await asyncio.wait_for(
                    self._call_task_func(task_info.func, *task_info.args, **task_info.kwargs),
                    timeout=task_info.timeout
                )
            else:
                task_result = await self._call_task_func(
                    task_info.func, *task_info.args, **task_info.kwargs
                )
            
            # Задача выполнена успешно
            task_info.status = TaskStatus.COMPLETED
            task_info.result = task_result
            task_info.completed_at = datetime.now()
            
            logger.debug(
                f"Задача {task_info.task_id} выполнена успешно "
                f"за {(task_info.completed_at - task_info.started_at).total_seconds():.2f} сек"
            )
            
            # Если задача периодическая, планируем следующее выполнение
            if task_info.periodic:
                task_info.schedule_next_run()
                self._pending_tasks.add(task_info.task_id)
            else:
                # Или удаляем выполненную задачу через некоторое время
                asyncio.create_task(self._cleanup_task(task_info.task_id, delay=3600))
        
        except asyncio.TimeoutError:
            task_info.status = TaskStatus.FAILED
            task_info.error = "Timeout exceeded"
            task_info.completed_at = datetime.now()
            
            logger.warning(f"Задача {task_info.task_id} превысила таймаут {task_info.timeout} сек")
            
            # Пробуем повторить, если разрешено
            await self._retry_task_if_needed(task_info)
        
        except Exception as e:
            task_info.status = TaskStatus.FAILED
            task_info.error = str(e)
            task_info.completed_at = datetime.now()
            
            logger.error(
                f"Ошибка при выполнении задачи {task_info.task_id}: {str(e)}",
                exc_info=True
            )
            
            # Пробуем повторить, если разрешено
            await self._retry_task_if_needed(task_info)
        
        finally:
            task_info._task = None
    
    async def _call_task_func(self, func: Callable, *args, **kwargs) -> Any:
        """
        Вызывает функцию задачи, учитывая, асинхронная она или нет
        
        Args:
            func: Функция для вызова
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Any: Результат выполнения функции
        """
        if asyncio.iscoroutinefunction(func):
            # Асинхронная функция
            return await func(*args, **kwargs)
        elif inspect.isgeneratorfunction(func):
            # Генераторная функция
            return list(func(*args, **kwargs))
        else:
            # Обычная функция
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                functools.partial(func, *args, **kwargs)
            )
    
    async def _retry_task_if_needed(self, task_info: TaskInfo) -> None:
        """
        Повторяет задачу, если разрешено и не превышено количество попыток
        
        Args:
            task_info: Информация о задаче
        """
        if not task_info.can_retry:
            return
        
        task_info.retry_count += 1
        task_info.status = TaskStatus.PENDING
        
        # Экспоненциальная задержка перед повторной попыткой (1s, 2s, 4s, 8s, ...)
        retry_delay = 2 ** (task_info.retry_count - 1)
        task_info.scheduled_at = datetime.now() + timedelta(seconds=retry_delay)
        
        logger.info(
            f"Задача {task_info.task_id} будет повторена (попытка {task_info.retry_count}) "
            f"через {retry_delay} сек"
        )
        
        self._pending_tasks.add(task_info.task_id)
    
    async def _cleanup_task(self, task_id: str, delay: int = 3600) -> None:
        """
        Удаляет информацию о задаче после задержки
        
        Args:
            task_id: Идентификатор задачи
            delay: Задержка в секундах (по умолчанию 1 час)
        """
        await asyncio.sleep(delay)
        
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.debug(f"Удалена информация о задаче {task_id}")
    
    async def add_task(
        self,
        func: Callable,
        *args,
        task_id: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
        delay: Optional[int] = None,
        periodic: bool = False,
        interval: Optional[int] = None,
        max_retries: int = 0,
        timeout: Optional[float] = None,
        priority: str = "normal",
        description: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Добавляет задачу в очередь
        
        Args:
            func: Функция для выполнения
            *args: Позиционные аргументы функции
            task_id: Идентификатор задачи (генерируется автоматически, если не указан)
            scheduled_at: Время планирования задачи
            delay: Задержка в секундах перед выполнением
            periodic: Периодическая ли задача
            interval: Интервал в секундах для периодических задач
            max_retries: Максимальное количество повторных попыток
            timeout: Таймаут выполнения в секундах
            priority: Приоритет задачи ('high', 'normal', 'low')
            description: Описание задачи для логирования
            **kwargs: Именованные аргументы функции
            
        Returns:
            str: Идентификатор задачи
        """
        # Генерируем ID задачи, если не указан
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # Определяем время выполнения
        if scheduled_at is None:
            if delay is not None:
                scheduled_at = datetime.now() + timedelta(seconds=delay)
            else:
                scheduled_at = datetime.now()
        
        # Проверяем приоритет
        if priority not in ['high', 'normal', 'low']:
            priority = 'normal'
        
        # Добавляем приоритет в аргументы
        kwargs['priority'] = priority
        
        # Проверяем интервал для периодических задач
        if periodic and interval is None:
            interval = 60  # Интервал по умолчанию - 1 минута
        
        # Создаем информацию о задаче
        task_info = TaskInfo(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            scheduled_at=scheduled_at,
            periodic=periodic,
            interval=interval,
            max_retries=max_retries,
            timeout=timeout,
            description=description
        )
        
        # Сохраняем задачу
        self._tasks[task_id] = task_info
        self._pending_tasks.add(task_id)
        
        logger.debug(
            f"Добавлена задача {task_id} ({description or func.__name__}), "
            f"запланирована на {scheduled_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return task_id
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Отменяет задачу
        
        Args:
            task_id: Идентификатор задачи
            
        Returns:
            bool: True, если задача была отменена, False иначе
        """
        if task_id not in self._tasks:
            return False
        
        task_info = self._tasks[task_id]
        
        # Если задача уже выполняется, отменяем её
        if task_info.status == TaskStatus.RUNNING and task_info._task:
            task_info._task.cancel()
        
        # Помечаем задачу как отмененную
        task_info.status = TaskStatus.CANCELLED
        
        # Удаляем из очереди ожидания
        if task_id in self._pending_tasks:
            self._pending_tasks.remove(task_id)
        
        logger.info(f"Задача {task_id} отменена")
        return True
    
    async def get_task_info(self, task_id: str) -> Optional[Dict]:
        """
        Получает информацию о задаче
        
        Args:
            task_id: Идентификатор задачи
            
        Returns:
            Optional[Dict]: Информация о задаче или None, если задача не найдена
        """
        if task_id not in self._tasks:
            return None
        
        task_info = self._tasks[task_id]
        
        # Преобразуем информацию в словарь
        return {
            "task_id": task_info.task_id,
            "status": task_info.status,
            "description": task_info.description,
            "created_at": task_info.created_at.isoformat(),
            "scheduled_at": task_info.scheduled_at.isoformat(),
            "started_at": task_info.started_at.isoformat() if task_info.started_at else None,
            "completed_at": task_info.completed_at.isoformat() if task_info.completed_at else None,
            "periodic": task_info.periodic,
            "interval": task_info.interval,
            "retry_count": task_info.retry_count,
            "max_retries": task_info.max_retries,
            "timeout": task_info.timeout,
            "result": task_info.result,
            "error": task_info.error
        }
    
    async def get_tasks(
        self, 
        status: Optional[Union[TaskStatus, List[TaskStatus]]] = None
    ) -> List[Dict]:
        """
        Получает список задач с фильтрацией по статусу
        
        Args:
            status: Статус или список статусов для фильтрации
            
        Returns:
            List[Dict]: Список информации о задачах
        """
        result = []
        
        for task_id, task_info in self._tasks.items():
            # Применяем фильтр по статусу, если указан
            if status:
                if isinstance(status, list):
                    if task_info.status not in status:
                        continue
                elif task_info.status != status:
                    continue
            
            # Добавляем информацию о задаче
            result.append(await self.get_task_info(task_id))
        
        return result
    
    async def get_stats(self) -> Dict:
        """
        Получает статистику задач
        
        Returns:
            Dict: Статистика задач
        """
        total = len(self._tasks)
        pending = len(self._pending_tasks)
        running = sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING)
        completed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)
        cancelled = sum(1 for t in self._tasks.values() if t.status == TaskStatus.CANCELLED)
        periodic = sum(1 for t in self._tasks.values() if t.periodic)
        
        return {
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "periodic": periodic,
            "workers": len(self._workers)
        }


# Создание глобального экземпляра менеджера задач
task_queue = TaskQueue()


# Декоратор для добавления задачи в очередь
def background_task(
    scheduled_at: Optional[datetime] = None,
    delay: Optional[int] = None,
    periodic: bool = False,
    interval: Optional[int] = None,
    max_retries: int = 0,
    timeout: Optional[float] = None,
    priority: str = "normal",
    description: Optional[str] = None
):
    """
    Декоратор для добавления функции в очередь фоновых задач
    
    Args:
        scheduled_at: Время планирования задачи
        delay: Задержка в секундах перед выполнением
        periodic: Периодическая ли задача
        interval: Интервал в секундах для периодических задач
        max_retries: Максимальное количество повторных попыток
        timeout: Таймаут выполнения в секундах
        priority: Приоритет задачи ('high', 'normal', 'low')
        description: Описание задачи
        
    Returns:
        Callable: Декоратор для функции
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await task_queue.add_task(
                func,
                *args,
                scheduled_at=scheduled_at,
                delay=delay,
                periodic=periodic,
                interval=interval,
                max_retries=max_retries,
                timeout=timeout,
                priority=priority,
                description=description,
                **kwargs
            )
        return wrapper
    return decorator 