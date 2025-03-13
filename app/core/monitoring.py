"""
Модуль для мониторинга системных ресурсов приложения
"""
import asyncio
import os
import threading
import time
from typing import Dict

import psutil

from app.core.logging import get_logger
from app.core.metrics import set_system_metrics

# Получение логгера
logger = get_logger("monitoring")


class ResourceMonitor:
    """
    Монитор системных ресурсов.
    
    Отслеживает использование CPU, памяти, диска и сети.
    Запускается в отдельном потоке и периодически проверяет ресурсы.
    """
    
    def __init__(
        self,
        interval: int = 60,
        memory_threshold_mb: int = 500,
        cpu_threshold_percent: int = 70
    ):
        """
        Инициализация монитора ресурсов
        
        Args:
            interval: Интервал проверки в секундах
            memory_threshold_mb: Пороговое значение памяти в МБ
            cpu_threshold_percent: Пороговое значение CPU в процентах
        """
        self.interval = interval
        self.memory_threshold = memory_threshold_mb * 1024 * 1024  # В байтах
        self.cpu_threshold = cpu_threshold_percent
        self._running = False
        self._thread = None
        self._process = psutil.Process(os.getpid())
    
    def start(self) -> None:
        """Запускает монитор ресурсов в отдельном потоке"""
        if self._running:
            logger.warning("Монитор ресурсов уже запущен")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="resource_monitor"
        )
        self._thread.start()
        logger.info("Монитор ресурсов запущен")
    
    def stop(self) -> None:
        """Останавливает монитор ресурсов"""
        if not self._running:
            logger.warning("Монитор ресурсов уже остановлен")
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Монитор ресурсов остановлен")
    
    def _monitor_loop(self) -> None:
        """Основной цикл мониторинга в отдельном потоке"""
        logger.info(f"Запущен цикл мониторинга ресурсов (интервал: {self.interval} сек)")
        
        while self._running:
            try:
                # Получаем данные об использовании ресурсов
                resources = self.get_resource_usage()
                
                # Обновляем метрики Prometheus
                memory_bytes = resources.get("memory", {}).get("rss", 0)
                cpu_percent = resources.get("cpu", {}).get("percent", 0)
                set_system_metrics(memory_bytes, cpu_percent)
                
                # Проверяем пороговые значения
                self._check_thresholds(resources)
                
                # Ждем следующей проверки
                time.sleep(self.interval)
            
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {str(e)}", exc_info=True)
                time.sleep(10)  # Пауза перед повторной попыткой
    
    def _check_thresholds(self, resources: Dict) -> None:
        """
        Проверяет пороговые значения использования ресурсов
        
        Args:
            resources: Словарь с данными об использовании ресурсов
        """
        # Проверка использования памяти
        memory_rss = resources.get("memory", {}).get("rss", 0)
        if memory_rss > self.memory_threshold:
            logger.warning(
                f"Использование памяти превышено: {memory_rss / (1024 * 1024):.2f} МБ "
                f"(порог: {self.memory_threshold / (1024 * 1024):.2f} МБ)"
            )
        
        # Проверка использования CPU
        cpu_percent = resources.get("cpu", {}).get("percent", 0)
        if cpu_percent > self.cpu_threshold:
            logger.warning(
                f"Использование CPU превышено: {cpu_percent:.2f}% "
                f"(порог: {self.cpu_threshold:.2f}%)"
            )
    
    def get_resource_usage(self) -> Dict:
        """
        Получает информацию об использовании системных ресурсов
        
        Returns:
            Dict: Словарь с данными об использовании ресурсов
        """
        try:
            # Обновляем информацию о процессе
            self._process.cpu_percent()
            time.sleep(0.1)  # Небольшая пауза для измерения CPU
            
            # Получаем информацию о CPU
            cpu_percent = self._process.cpu_percent()
            cpu_times = self._process.cpu_times()
            
            # Получаем информацию о памяти
            memory_info = self._process.memory_info()
            
            # Получаем информацию о дисковых операциях
            io_counters = self._process.io_counters() if hasattr(self._process, 'io_counters') else None
            
            # Получаем информацию о сетевых подключениях
            connections = len(self._process.connections())
            
            # Получаем информацию о потоках и дочерних процессах
            threads = len(self._process.threads())
            children = len(self._process.children())
            
            # Формируем словарь с результатами
            result = {
                "cpu": {
                    "percent": cpu_percent,
                    "user": cpu_times.user,
                    "system": cpu_times.system
                },
                "memory": {
                    "rss": memory_info.rss,  # Физическая память (RAM)
                    "vms": memory_info.vms,  # Виртуальная память
                    "percent": self._process.memory_percent()
                },
                "connections": connections,
                "threads": threads,
                "children": children,
                "timestamp": time.time()
            }
            
            # Добавляем информацию о дисковых операциях, если доступна
            if io_counters:
                result["io"] = {
                    "read_count": io_counters.read_count,
                    "write_count": io_counters.write_count,
                    "read_bytes": io_counters.read_bytes,
                    "write_bytes": io_counters.write_bytes
                }
            
            return result
        
        except Exception as e:
            logger.error(f"Ошибка при получении информации о ресурсах: {str(e)}", exc_info=True)
            return {}


# Асинхронная функция для получения информации о ресурсах
async def get_resources() -> Dict:
    """
    Асинхронная функция для получения информации о системных ресурсах
    
    Returns:
        Dict: Словарь с данными об использовании ресурсов
    """
    # Создаем временный монитор для получения данных
    monitor = ResourceMonitor()
    
    # Выполняем получение данных в отдельном потоке
    loop = asyncio.get_event_loop()
    resource_data = await loop.run_in_executor(None, monitor.get_resource_usage)
    
    return resource_data 