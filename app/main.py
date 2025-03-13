"""
Основной модуль приложения - точка входа FastAPI
"""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.metrics import setup_metrics
from app.core.monitoring import ResourceMonitor
from app.core.redis import redis_manager
from app.core.tasks import task_queue
from app.db.database import init_db

# Настройка логирования
setup_logging(log_level=settings.LOG_LEVEL)

# Получение логгера
logger = get_logger("main")

# Контекст запуска приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекст жизненного цикла приложения
    Запускается при старте и остановке приложения
    """
    # Запуск компонентов
    logger.info("Запуск приложения...")
    
    # Инициализация Redis
    await redis_manager.initialize()
    logger.info("Redis инициализирован")
    
    # Запуск монитора ресурсов
    if settings.ENABLE_MONITORING:
        resource_monitor = ResourceMonitor(
            interval=settings.MONITORING_INTERVAL,
            memory_threshold_mb=settings.MEMORY_THRESHOLD_MB,
            cpu_threshold_percent=settings.CPU_THRESHOLD_PERCENT
        )
        resource_monitor.start()
        logger.info(f"Мониторинг ресурсов запущен (интервал: {settings.MONITORING_INTERVAL} сек)")
    
    # Инициализация базы данных
    await init_db()
    logger.info("База данных инициализирована")
    
    # Запуск планировщика задач
    await task_queue.start()
    logger.info("Планировщик задач запущен")
    
    # Создаем теневую задачу для периодической очистки сессий в Redis
    await task_queue.add_task(
        redis_manager.clean_inactive_sessions,
        scheduled_at=None,
        periodic=True,
        interval=settings.CLEANUP_INTERVAL,
        description="Очистка неактивных сессий"
    )
    
    # Yield для передачи управления приложению
    yield
    
    # Остановка компонентов при завершении
    logger.info("Остановка приложения...")
    
    # Остановка планировщика задач
    await task_queue.stop()
    logger.info("Планировщик задач остановлен")
    
    # Закрытие соединения с Redis
    await redis_manager.close()
    logger.info("Соединение с Redis закрыто")
    
    # Остановка монитора ресурсов
    if settings.ENABLE_MONITORING:
        resource_monitor.stop()
        logger.info("Мониторинг ресурсов остановлен")


# Создание приложения FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка сбора метрик Prometheus
if settings.METRICS_ENABLED:
    setup_metrics(app)
    logger.info("Метрики Prometheus настроены")

# Обработчик необработанных исключений
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений"""
    logger.error(f"Необработанное исключение: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Внутренняя ошибка сервера"}
    )

# Включение маршрутов API
app.include_router(api_router, prefix=settings.API_V1_STR)

# Маршрут для проверки работоспособности
@app.get("/health", tags=["health"])
async def health_check():
    """Проверка работоспособности приложения"""
    return {"status": "ok", "environment": settings.ENVIRONMENT}


# Запуск приложения с uvicorn при прямом запуске модуля
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT.lower() == "development"
    ) 