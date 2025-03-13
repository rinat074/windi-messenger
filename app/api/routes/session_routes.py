"""
Маршруты для управления сессиями пользователей (для функциональности авторизации на нескольких устройствах)
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.core.performance import async_time_it
from app.core.session import session_manager
from app.db.models.user import User
from app.schemas.session import (
    SessionDeviceInfo, 
    SessionListResponse, 
    SessionResponse, 
    SessionTerminateRequest
)

# Создание маршрутизатора
router = APIRouter(prefix=f"{settings.API_V1_STR}/sessions", tags=["sessions"])

# Получение логгера
logger = get_logger("session_routes")


@router.get(
    "", 
    response_model=SessionListResponse,
    summary="Получение списка активных сессий",
    description="""
    Возвращает список всех активных сессий текущего пользователя.
    Для каждой сессии отображается информация об устройстве и времени последней активности.
    Пользователь может видеть, с каких устройств он авторизован в системе.
    """
)
@async_time_it
async def get_sessions(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Получение списка активных сессий пользователя
    """
    # Получаем все сессии пользователя
    user_sessions = session_manager.get_user_sessions(str(current_user.id))
    
    # Текущая сессия
    current_session_id = request.cookies.get("session_id")
    
    # Формируем ответ
    sessions = []
    for session in user_sessions:
        # Пропускаем неактивные сессии
        if not session.is_active:
            continue
            
        sessions.append(SessionResponse(
            session_id=session.session_id,
            device_info=SessionDeviceInfo(
                device_id=session.device_info.device_id,
                device_name=session.device_info.device_name,
                ip_address=session.device_info.ip_address,
                user_agent=session.device_info.user_agent,
                last_active=session.device_info.last_active
            ),
            is_current=session.session_id == current_session_id,
            is_active=session.is_active,
            created_at=session.device_info.created_at
        ))
    
    # Сортируем по времени последней активности (новые сверху)
    sessions.sort(key=lambda s: s.device_info.last_active, reverse=True)
    
    logger.debug(f"Пользователь {current_user.id} запросил список своих сессий")
    return SessionListResponse(
        sessions=sessions,
        active_count=len(sessions),
        total_count=len(user_sessions)
    )


@router.post(
    "/terminate", 
    status_code=status.HTTP_200_OK,
    summary="Завершение сессии",
    description="""
    Позволяет завершить указанную сессию или все сессии кроме текущей.
    После завершения сессии пользователь будет вынужден авторизоваться заново на устройстве.
    """
)
@async_time_it
async def terminate_session(
    terminate_data: SessionTerminateRequest,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Завершение сессии пользователя
    """
    # Получаем текущую сессию
    current_session_id = request.cookies.get("session_id")
    
    # Проверяем, что пользователь не пытается завершить свою текущую сессию
    if terminate_data.session_id == current_session_id and not terminate_data.terminate_all_except_current:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя завершить текущую сессию. Используйте выход из системы."
        )
    
    # Получаем все сессии пользователя
    user_sessions = session_manager.get_user_sessions(str(current_user.id))
    
    if terminate_data.terminate_all_except_current:
        # Завершаем все сессии кроме текущей
        terminated_count = 0
        for session in user_sessions:
            if session.session_id != current_session_id and session.is_active:
                session_manager.terminate_session(session.session_id)
                terminated_count += 1
        
        logger.info(f"Пользователь {current_user.id} завершил все сессии кроме текущей: {terminated_count} сессий")
        return {
            "message": f"Завершено {terminated_count} сессий",
            "terminated_count": terminated_count
        }
    else:
        # Проверяем, что завершаемая сессия принадлежит текущему пользователю
        session_to_terminate = None
        for session in user_sessions:
            if session.session_id == terminate_data.session_id:
                session_to_terminate = session
                break
        
        if not session_to_terminate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Сессия не найдена"
            )
        
        # Завершаем сессию
        session_manager.terminate_session(terminate_data.session_id)
        
        logger.info(
            f"Пользователь {current_user.id} завершил сессию {terminate_data.session_id} "
            f"(устройство: {session_to_terminate.device_info.device_name})"
        )
        return {
            "message": "Сессия успешно завершена",
            "terminated_session_id": terminate_data.session_id
        } 