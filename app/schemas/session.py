"""
Схемы для работы с сессиями пользователей
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SessionDeviceInfo(BaseModel):
    """Информация об устройстве для API-ответов"""
    device_id: str
    device_name: str
    ip_address: str
    user_agent: str
    last_active: datetime


class SessionResponse(BaseModel):
    """Информация о сессии для API-ответов"""
    session_id: str
    device_info: SessionDeviceInfo
    is_current: bool
    is_active: bool
    created_at: datetime


class SessionListResponse(BaseModel):
    """Список сессий пользователя"""
    sessions: List[SessionResponse]
    active_count: int
    total_count: int


class SessionTerminateRequest(BaseModel):
    """Запрос на завершение сессии"""
    session_id: str
    terminate_all_except_current: bool = Field(
        default=False, 
        description="Завершить все сессии кроме текущей"
    )


class DeviceRegistrationRequest(BaseModel):
    """Запрос на регистрацию устройства"""
    device_name: str = Field(..., min_length=1, max_length=100)
    device_token: Optional[str] = Field(
        default=None, 
        description="Токен устройства для push-уведомлений"
    ) 