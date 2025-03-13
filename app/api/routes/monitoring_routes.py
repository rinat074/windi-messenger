"""
Маршруты для мониторинга состояния приложения
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_current_user, admin_only
from app.core.config import settings
from app.core.logging import get_logger
from app.core.monitoring import get_resources
from app.core.performance import async_time_it
from app.core.redis import redis_manager
from app.core.tasks import task_queue
from app.db.models.user import User

# Создание маршрутизатора
router = APIRouter(prefix=f"{settings.API_V1_STR}/monitoring", tags=["monitoring"])

# Получение логгера
logger = get_logger("monitoring_routes")


@router.get(
    "/resources",
    summary="Получение информации о системных ресурсах",
    description="Возвращает информацию об использовании CPU, памяти и других системных ресурсов."
)
@async_time_it
async def resources(
    current_user: User = Depends(admin_only)
):
    """
    Получение информации о системных ресурсах
    Доступно только администраторам
    """
    resource_data = await get_resources()
    return resource_data


@router.get(
    "/stats",
    summary="Статистика приложения",
    description="Возвращает общую статистику приложения."
)
@async_time_it
async def app_stats(
    current_user: User = Depends(get_current_user)
):
    """Получение статистики приложения"""
    
    # Получаем статистику задач
    task_stats = await task_queue.get_stats()
    
    # Получаем статистику сессий
    try:
        session_keys = await redis_manager._redis.keys(f"{redis_manager.SESSION_PREFIX}*")
        session_count = len(session_keys)
    except:
        session_count = 0
    
    # Получаем количество онлайн-пользователей
    try:
        online_users = await redis_manager.get_online_users()
        online_count = len(online_users)
    except:
        online_count = 0
    
    # Формируем статистику
    stats = {
        "sessions": {
            "active": session_count,
            "online_users": online_count
        },
        "tasks": task_stats,
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT
    }
    
    return stats


@router.get(
    "/status",
    summary="Статус компонентов",
    description="Проверяет состояние всех компонентов системы."
)
@async_time_it
async def system_status(
    current_user: User = Depends(admin_only)
):
    """
    Проверка состояния компонентов системы
    Доступно только администраторам
    """
    status = {
        "api": "ok",
        "database": "unknown",
        "redis": "unknown",
        "task_queue": "unknown",
    }
    
    # Проверяем Redis
    try:
        await redis_manager.ensure_connection()
        await redis_manager._redis.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"error: {str(e)}"
    
    # Проверяем очередь задач
    try:
        task_stats = await task_queue.get_stats()
        if task_stats.get("workers", 0) > 0:
            status["task_queue"] = "ok"
        else:
            status["task_queue"] = "no_workers"
    except Exception as e:
        status["task_queue"] = f"error: {str(e)}"
    
    # Общий статус
    if all(s == "ok" for s in status.values()):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "healthy", "components": status}
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "components": status}
        ) 