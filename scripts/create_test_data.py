#!/usr/bin/env python3
"""
Скрипт для создания тестовых данных в базе данных.

Этот скрипт генерирует тестовых пользователей, чаты и сообщения
для целей тестирования и разработки.

Использование:
    python scripts/create_test_data.py
"""

import os
import sys
import uuid
import random
import string
import asyncio
import argparse
import datetime
from typing import List, Dict, Any

import httpx
from dotenv import load_dotenv
from passlib.context import CryptContext

# Настроим путь для импорта модулей приложения
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Импортируем необходимые модули приложения
try:
    from app.db.database import get_db
    from app.db.models.user import User
    from app.db.models.chat import Chat, ChatUser
    from app.db.models.message import Message
    from app.core.auth import get_password_hash
except ImportError as e:
    print(f"Ошибка импорта модулей приложения: {e}")
    print("Убедитесь, что вы запускаете скрипт из корневого каталога проекта")
    sys.exit(1)

# Загружаем переменные окружения
load_dotenv()

# Настройки для генерации данных
NUM_USERS = 10
NUM_CHATS = 5
MESSAGES_PER_CHAT = 20
DEFAULT_PASSWORD = "Password123!"
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

# Инструмент для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_test_users(db) -> List[User]:
    """Создает тестовых пользователей в базе данных"""
    print(f"Создание {NUM_USERS} тестовых пользователей...")
    
    users = []
    for i in range(1, NUM_USERS + 1):
        user = User(
            email=f"user{i}@example.com",
            username=f"user{i}",
            hashed_password=get_password_hash(DEFAULT_PASSWORD),
            is_active=True,
            is_superuser=i == 1,  # Первый пользователь - админ
            created_at=datetime.datetime.utcnow()
        )
        db.add(user)
        users.append(user)
    
    await db.commit()
    
    # Обновляем пользователей с их новыми ID
    for user in users:
        await db.refresh(user)
    
    print(f"Создано {len(users)} пользователей")
    return users


async def create_test_chats(db, users: List[User]) -> List[Chat]:
    """Создает тестовые чаты между пользователями"""
    print(f"Создание {NUM_CHATS} тестовых чатов...")
    
    chats = []
    
    # Создаем групповой чат со всеми пользователями
    general_chat = Chat(
        name="Общий чат",
        is_private=False,
        created_at=datetime.datetime.utcnow(),
        created_by=users[0].id
    )
    db.add(general_chat)
    await db.flush()
    
    # Добавляем всех пользователей в общий чат
    for user in users:
        chat_user = ChatUser(
            chat_id=general_chat.id,
            user_id=user.id,
            joined_at=datetime.datetime.utcnow()
        )
        db.add(chat_user)
    
    chats.append(general_chat)
    
    # Создаем несколько случайных групповых чатов
    for i in range(1, NUM_CHATS):
        # Случайное количество участников (минимум 2)
        num_participants = random.randint(2, min(5, len(users)))
        participants = random.sample(users, num_participants)
        
        chat = Chat(
            name=f"Тестовый чат {i}",
            is_private=False,
            created_at=datetime.datetime.utcnow(),
            created_by=participants[0].id
        )
        db.add(chat)
        await db.flush()
        
        # Добавляем участников
        for user in participants:
            chat_user = ChatUser(
                chat_id=chat.id,
                user_id=user.id,
                joined_at=datetime.datetime.utcnow()
            )
            db.add(chat_user)
        
        chats.append(chat)
    
    # Создаем несколько личных чатов между парами пользователей
    for i in range(NUM_CHATS - 1):
        user1, user2 = random.sample(users, 2)
        
        chat = Chat(
            name=None,  # У личных чатов нет имени
            is_private=True,
            created_at=datetime.datetime.utcnow(),
            created_by=user1.id
        )
        db.add(chat)
        await db.flush()
        
        # Добавляем двух участников
        for user in [user1, user2]:
            chat_user = ChatUser(
                chat_id=chat.id,
                user_id=user.id,
                joined_at=datetime.datetime.utcnow()
            )
            db.add(chat_user)
        
        chats.append(chat)
    
    await db.commit()
    
    # Обновляем чаты с их новыми ID
    for chat in chats:
        await db.refresh(chat)
    
    print(f"Создано {len(chats)} чатов")
    return chats


async def create_test_messages(db, chats: List[Chat], users: List[User]) -> None:
    """Создает тестовые сообщения в чатах"""
    print(f"Создание тестовых сообщений в чатах...")
    
    total_messages = 0
    
    # Текстовые фразы для генерации сообщений
    phrases = [
        "Привет, как дела?",
        "Что нового?",
        "Когда встречаемся?",
        "Проверка Centrifugo",
        "Это тестовое сообщение",
        "WinDI Messenger работает отлично!",
        "Тестируем интеграцию с Centrifugo",
        "Добрый день всем!",
        "Сегодня отличная погода",
        "Кто-нибудь может помочь с тестированием?",
        "Новое сообщение в чате",
        "Я только что подключился"
    ]
    
    for chat in chats:
        # Получаем список участников чата
        query = db.query(ChatUser).filter(ChatUser.chat_id == chat.id)
        chat_users = await query.all()
        participant_ids = [cu.user_id for cu in chat_users]
        
        # Определяем количество сообщений для этого чата
        num_messages = random.randint(MESSAGES_PER_CHAT // 2, MESSAGES_PER_CHAT * 2)
        
        # Случайное время за последние 7 дней
        now = datetime.datetime.utcnow()
        start_time = now - datetime.timedelta(days=7)
        
        for i in range(num_messages):
            # Случайный отправитель из участников чата
            sender_id = random.choice(participant_ids)
            
            # Случайное время отправки
            sent_time = start_time + datetime.timedelta(
                seconds=random.randint(0, int((now - start_time).total_seconds()))
            )
            
            # Случайное сообщение
            text = random.choice(phrases)
            
            # Иногда добавляем случайный текст для разнообразия
            if random.random() < 0.3:
                random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                text += f" (случайный текст: {random_suffix})"
            
            message = Message(
                chat_id=chat.id,
                sender_id=sender_id,
                text=text,
                client_message_id=f"test_{uuid.uuid4().hex[:8]}",
                is_read=random.random() < 0.7,  # 70% сообщений прочитаны
                created_at=sent_time,
                updated_at=sent_time
            )
            db.add(message)
            total_messages += 1
        
        # Сохраняем сообщения для текущего чата
        await db.commit()
    
    print(f"Создано {total_messages} сообщений в {len(chats)} чатах")


async def create_api_users() -> List[Dict[str, Any]]:
    """Создает тестовых пользователей через API"""
    print(f"Создание тестовых пользователей через API...")
    
    users = []
    async with httpx.AsyncClient() as client:
        for i in range(1, NUM_USERS + 1):
            try:
                response = await client.post(
                    f"{API_URL}/users/register",
                    json={
                        "email": f"user{i}@example.com",
                        "username": f"user{i}",
                        "password": DEFAULT_PASSWORD
                    }
                )
                
                if response.status_code in (200, 201):
                    user_data = response.json()
                    print(f"Создан пользователь user{i}@example.com с ID: {user_data.get('id')}")
                    users.append(user_data)
                else:
                    print(f"Не удалось создать пользователя user{i}@example.com: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Ошибка при создании пользователя user{i}@example.com: {str(e)}")
    
    print(f"Создано {len(users)} пользователей через API")
    return users


async def create_api_chats(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Создает тестовые чаты через API"""
    if not users:
        print("Нет пользователей для создания чатов")
        return []
    
    print(f"Создание тестовых чатов через API...")
    
    # Получаем токен для первого пользователя для создания чатов
    async with httpx.AsyncClient() as client:
        auth_response = await client.post(
            f"{API_URL}/users/login",
            json={
                "email": users[0]["email"],
                "password": DEFAULT_PASSWORD
            }
        )
        
        if auth_response.status_code != 200:
            print(f"Не удалось войти в систему: {auth_response.status_code} - {auth_response.text}")
            return []
        
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        chats = []
        
        # Создаем общий чат со всеми пользователями
        user_ids = [user["id"] for user in users]
        general_chat_response = await client.post(
            f"{API_URL}/chats",
            json={
                "name": "Общий чат API",
                "participants": user_ids,
                "is_private": False
            },
            headers=headers
        )
        
        if general_chat_response.status_code in (200, 201):
            general_chat = general_chat_response.json()
            print(f"Создан общий чат: {general_chat.get('name')} с ID: {general_chat.get('id')}")
            chats.append(general_chat)
        else:
            print(f"Не удалось создать общий чат: {general_chat_response.status_code} - {general_chat_response.text}")
        
        # Создаем несколько групповых чатов
        for i in range(1, NUM_CHATS):
            num_participants = random.randint(2, min(5, len(users)))
            participants = random.sample(user_ids, num_participants)
            
            chat_response = await client.post(
                f"{API_URL}/chats",
                json={
                    "name": f"Тестовый API чат {i}",
                    "participants": participants,
                    "is_private": False
                },
                headers=headers
            )
            
            if chat_response.status_code in (200, 201):
                chat = chat_response.json()
                print(f"Создан групповой чат: {chat.get('name')} с ID: {chat.get('id')}")
                chats.append(chat)
            else:
                print(f"Не удалось создать групповой чат: {chat_response.status_code} - {chat_response.text}")
        
        print(f"Создано {len(chats)} чатов через API")
        return chats


async def main(use_api: bool = False, confirm: bool = True):
    """Основная функция для создания тестовых данных"""
    print("===== Генератор тестовых данных для WinDI Messenger =====")
    
    if use_api:
        print("Создание данных через API...")
        
        if confirm:
            response = input("Это может привести к созданию дублирующихся записей. Продолжить? (y/n): ")
            if response.lower() != 'y':
                print("Отмена операции")
                return
        
        users = await create_api_users()
        chats = await create_api_chats(users)
        print("Данные успешно созданы через API")
    else:
        print("Создание данных напрямую в базе данных...")
        
        if confirm:
            response = input("Это может перезаписать существующие данные. Продолжить? (y/n): ")
            if response.lower() != 'y':
                print("Отмена операции")
                return
        
        # Получаем сессию базы данных
        async for db in get_db():
            # Создаем тестовые данные
            users = await create_test_users(db)
            chats = await create_test_chats(db, users)
            await create_test_messages(db, chats, users)
            break
        
        print("Данные успешно созданы в базе данных")
    
    print(f"""
Тестовые учетные данные:
========================
Для всех пользователей пароль: {DEFAULT_PASSWORD}

Пользователи:
- user1@example.com (администратор)
- user2@example.com
- ...
- user{NUM_USERS}@example.com

Чаты:
- Общий чат (все пользователи)
- Несколько групповых чатов
- Несколько личных чатов

Вы можете использовать эти данные для тестирования Centrifugo.
===============================================================
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Генератор тестовых данных для WinDI Messenger")
    parser.add_argument("--api", action="store_true", help="Создать данные через API вместо прямого доступа к базе данных")
    parser.add_argument("--force", action="store_true", help="Пропустить подтверждение")
    args = parser.parse_args()
    
    asyncio.run(main(use_api=args.api, confirm=not args.force)) 