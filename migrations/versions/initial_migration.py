"""Initial migration

Revision ID: aa92fd2a3b6f
Revises: 
Create Date: 2023-03-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


# revision identifiers, used by Alembic.
revision = 'aa92fd2a3b6f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создание таблицы пользователей
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    
    # Создание таблицы чатов
    op.create_table(
        'chats',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('type', sa.String(10), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    
    # Создание связующей таблицы пользователей и чатов
    op.create_table(
        'user_chat',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('chat_id', UUID(as_uuid=True), sa.ForeignKey('chats.id'), primary_key=True),
    )
    
    # Создание таблицы сообщений
    op.create_table(
        'messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('chat_id', UUID(as_uuid=True), sa.ForeignKey('chats.id'), nullable=False),
        sa.Column('sender_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('is_read', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('client_message_id', sa.String(100), nullable=True, index=True),
    )


def downgrade() -> None:
    # Удаление всех созданных таблиц в обратном порядке
    op.drop_table('messages')
    op.drop_table('user_chat')
    op.drop_table('chats')
    op.drop_table('users') 