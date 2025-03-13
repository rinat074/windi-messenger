import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class ChatType(str, PyEnum):
    """Типы чатов в системе"""
    DIRECT = "direct"  # Личный чат между двумя пользователями
    GROUP = "group"    # Групповой чат с множеством участников


# Связующая таблица для пользователей и чатов (многие-ко-многим)
user_chat = Table(
    "user_chat",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("chat_id", UUID(as_uuid=True), ForeignKey("chats.id"), primary_key=True)
)


class Chat(Base):
    """Модель чата (как личного, так и группового)"""
    __tablename__ = "chats"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=True)  # Только для групповых чатов
    type = Column(Enum(ChatType), nullable=False, default=ChatType.DIRECT)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Отношения
    users = relationship("User", secondary=user_chat, back_populates="chats")
    messages = relationship("Message", back_populates="chat") 