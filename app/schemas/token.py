"""
Схемы для токенов авторизации и Centrifugo
"""
from typing import Optional
from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Схема ответа с токеном доступа"""
    token: str


class TokenDetailsResponse(BaseModel):
    """Схема ответа с токеном доступа и дополнительной информацией"""
    access_token: str
    token_type: str = "bearer"
    session_id: str


class CentrifugoTokenResponse(BaseModel):
    """Схема ответа с токеном для подключения к Centrifugo"""
    token: str
    expires_at: Optional[int] = None
    
    class Config:
        schema_extra = {
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expires_at": 1716508800
            }
        }


class CentrifugoChannelTokenResponse(BaseModel):
    """Схема ответа с токеном для подписки на канал Centrifugo"""
    token: str
    channel: str
    expires_at: Optional[int] = None
    
    class Config:
        schema_extra = {
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "channel": "chat:1",
                "expires_at": 1716508800
            }
        }


class CentrifugoConnectionInfo(BaseModel):
    """Схема информации о подключении к Centrifugo"""
    ws_url: str = Field(..., description="URL для подключения по WebSocket")
    http_url: str = Field(..., description="URL для подключения по HTTP")
    token: str = Field(..., description="Токен для подключения")
    version: str = Field("3.0", description="Версия Centrifugo API")
    expires_at: Optional[int] = Field(None, description="Время истечения токена в формате Unix timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "ws_url": "ws://localhost:8001/connection/websocket",
                "http_url": "http://localhost:8001/connection/http_stream",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "version": "3.0",
                "expires_at": 1716508800
            }
        } 