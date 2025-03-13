"""
Схемы для работы с сообщениями, историей чатов и сообщениями Centrifugo
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, root_validator


class AttachmentType(str, Enum):
    """Типы вложений к сообщениям"""
    
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    VOICE = "voice"
    LOCATION = "location"
    CONTACT = "contact"
    OTHER = "other"


class AttachmentMetadata(BaseModel):
    """Метаданные вложения в зависимости от типа"""
    
    # Для изображений и видео
    width: Optional[int] = None
    height: Optional[int] = None
    
    # Для аудио и видео
    duration: Optional[int] = None  # в секундах
    
    # Для документов
    page_count: Optional[int] = None
    
    # Для местоположений
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Для контактов
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class Attachment(BaseModel):
    """Вложение к сообщению"""
    
    id: Optional[UUID] = None
    type: AttachmentType
    filename: str
    size: int  # в байтах
    mime_type: str
    url: HttpUrl
    thumbnail_url: Optional[HttpUrl] = None
    metadata: Optional[AttachmentMetadata] = None
    
    class Config:
        orm_mode = True


class MessageBase(BaseModel):
    """Базовая модель сообщения"""
    
    text: Optional[str] = Field(None, min_length=1, max_length=4000)
    attachments: List[Attachment] = []
    
    class Config:
        extra = "forbid"
    
    @root_validator
    def validate_content(cls, values):
        """Проверяет, что сообщение содержит текст или вложения"""
        text = values.get("text")
        attachments = values.get("attachments")
        if not text and not attachments:
            raise ValueError("Сообщение должно содержать текст или вложения")
        return values


class MessageCreate(MessageBase):
    """Создание нового сообщения"""
    
    chat_id: Optional[UUID] = None  # Может быть опциональным, если передается в URL
    client_message_id: Optional[str] = None  # Идентификатор на стороне клиента


class MessageReadEvent(BaseModel):
    """Событие прочтения сообщения"""
    
    message_id: UUID


class ReadReceipt(BaseModel):
    """Подтверждение прочтения сообщения"""
    
    message_id: UUID
    chat_id: UUID
    user_id: UUID
    timestamp: datetime


class TypingEvent(BaseModel):
    """Событие начала/окончания печати"""
    
    chat_id: UUID
    user_id: UUID
    user_name: str
    is_typing: bool
    timestamp: str  # ISO формат datetime


class MessageResponse(BaseModel):
    """Ответ с данными сообщения"""
    
    id: UUID
    chat_id: UUID
    sender_id: UUID
    text: Optional[str] = None
    attachments: List[Attachment] = []
    created_at: datetime
    updated_at: datetime
    is_read: bool
    client_message_id: Optional[str] = None
    
    class Config:
        orm_mode = True


class MessageList(BaseModel):
    """Список сообщений с пагинацией"""
    
    items: List[MessageResponse]
    total: int
    has_more: bool
    next_cursor: Optional[str] = None  # Курсор для следующей страницы


class MessageHistoryParams(BaseModel):
    """Параметры для запроса истории сообщений"""
    
    limit: int = Field(50, ge=1, le=100)
    before_id: Optional[UUID] = None
    after_id: Optional[UUID] = None
    include_deleted: bool = False


class MessageStatus(str, Enum):
    """Статусы сообщений"""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageType(str, Enum):
    """Типы сообщений"""
    TEXT = "text"
    SYSTEM = "system"
    SERVICE = "service"


class MessageOut(BaseModel):
    """Модель для вывода сообщения"""
    id: int = Field(..., description="Уникальный идентификатор сообщения")
    chat_id: int = Field(..., description="ID чата")
    sender_id: int = Field(..., description="ID отправителя")
    sender_name: Optional[str] = Field(None, description="Имя отправителя")
    created_at: datetime = Field(..., description="Время создания сообщения")
    updated_at: Optional[datetime] = Field(None, description="Время последнего обновления сообщения")
    is_edited: bool = Field(False, description="Флаг, было ли сообщение отредактировано")
    status: MessageStatus = Field(MessageStatus.SENT, description="Статус сообщения")
    reply_to_id: Optional[int] = Field(None, description="ID сообщения, на которое отвечает это сообщение")
    reply_to: Optional[Dict[str, Any]] = Field(None, description="Информация о сообщении, на которое это сообщение отвечает")
    client_id: Optional[str] = Field(None, description="Клиентский ID сообщения")


class CentrifugoMessageData(BaseModel):
    """Модель сообщения для отправки через Centrifugo"""
    id: str = Field(..., description="Уникальный идентификатор сообщения")
    content: str = Field(..., description="Текст сообщения")
    sender_id: str = Field(..., description="ID отправителя")
    sender_name: str = Field(..., description="Имя отправителя")
    timestamp: int = Field(..., description="Временная метка отправки в формате Unix timestamp")
    message_type: str = Field("text", description="Тип сообщения")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="Вложения сообщения")
    chat_id: str = Field(..., description="ID чата")
    client_id: Optional[str] = Field(None, description="Клиентский ID сообщения")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Дополнительные метаданные")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "msg_123456",
                "content": "Привет, как дела?",
                "sender_id": "1",
                "sender_name": "Иван Петров",
                "timestamp": 1653308231,
                "message_type": "text",
                "attachments": [],
                "chat_id": "1",
                "client_id": "client_msg_123456"
            }
        }


class CentrifugoServiceMessage(BaseModel):
    """Модель сервисного сообщения для отправки через Centrifugo"""
    type: str = Field(..., description="Тип сервисного сообщения (typing, user_status и т.д.)")
    sender_id: str = Field(..., description="ID пользователя, который вызвал событие")
    sender_name: Optional[str] = Field(None, description="Имя пользователя")
    data: Dict[str, Any] = Field(..., description="Данные сервисного сообщения")
    timestamp: int = Field(..., description="Временная метка отправки в формате Unix timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "type": "typing",
                "sender_id": "1",
                "sender_name": "Иван Петров",
                "data": {"is_typing": True},
                "timestamp": 1653308231
            }
        } 