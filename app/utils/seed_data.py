import asyncio
import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal, Base, engine
from app.db.models.chat import Chat, ChatType, user_chat
from app.db.models.message import Message
from app.db.models.user import User

# Тестовые данные
TEST_USERS = [
    {"name": "Иван Иванов", "email": "ivan@example.com", "password": "password123"},
    {"name": "Мария Петрова", "email": "maria@example.com", "password": "password123"},
    {"name": "Алексей Сидоров", "email": "alex@example.com", "password": "password123"},
    {"name": "Елена Смирнова", "email": "elena@example.com", "password": "password123"},
    {"name": "Дмитрий Козлов", "email": "dmitry@example.com", "password": "password123"},
]

TEST_MESSAGES = [
    "Привет! Как дела?",
    "Что нового?",
    "Встретимся сегодня?",
    "Спасибо за информацию!",
    "Посмотри, что я нашел!",
    "Когда у нас дедлайн?",
    "Можешь помочь с задачей?",
    "Отличная работа!",
    "Это интересно!",
    "Завтра созвон в 10:00",
    "Не забудь прислать отчет",
    "Хорошего дня!",
]


async def create_tables():
    """Создание всех таблиц в базе данных"""
    async with engine.begin() as conn:
        # Удаление существующих таблиц
        await conn.run_sync(Base.metadata.drop_all)
        # Создание таблиц заново
        await conn.run_sync(Base.metadata.create_all)


async def seed_users(db: AsyncSession):
    """Создание тестовых пользователей"""
    print("Создание пользователей...")
    users = []
    
    for user_data in TEST_USERS:
        user = User(
            name=user_data["name"],
            email=user_data["email"],
            password_hash=get_password_hash(user_data["password"])
        )
        db.add(user)
        users.append(user)
    
    await db.commit()
    return users


async def seed_chats(db: AsyncSession, users):
    """Создание тестовых чатов"""
    print("Создание чатов...")
    chats = []
    
    # Создание личных чатов (каждый с каждым)
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            chat = Chat(type=ChatType.DIRECT)
            db.add(chat)
            await db.flush()
            
            # Добавление пользователей в чат
            stmt1 = user_chat.insert().values(user_id=users[i].id, chat_id=chat.id)
            stmt2 = user_chat.insert().values(user_id=users[j].id, chat_id=chat.id)
            await db.execute(stmt1)
            await db.execute(stmt2)
            
            chats.append(chat)
    
    # Создание одного группового чата со всеми пользователями
    group_chat = Chat(
        name="Общий чат",
        type=ChatType.GROUP
    )
    db.add(group_chat)
    await db.flush()
    
    # Добавление всех пользователей в групповой чат
    for user in users:
        stmt = user_chat.insert().values(user_id=user.id, chat_id=group_chat.id)
        await db.execute(stmt)
    
    chats.append(group_chat)
    
    await db.commit()
    return chats


async def seed_messages(db: AsyncSession, users, chats):
    """Создание тестовых сообщений"""
    print("Создание сообщений...")
    messages = []
    
    # Генерация случайных сообщений для каждого чата
    for chat in chats:
        # Получение пользователей чата
        chat_users = []
        for user in users:
            stmt = user_chat.select().where(
                user_chat.c.chat_id == chat.id, 
                user_chat.c.user_id == user.id
            )
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                chat_users.append(user)
        
        # Генерация от 5 до 15 сообщений для каждого чата
        message_count = random.randint(5, 15)
        
        now = datetime.utcnow()
        for i in range(message_count):
            sender = random.choice(chat_users)
            created_at = now - timedelta(minutes=random.randint(1, 60 * 24 * 5))  # За последние 5 дней
            
            message = Message(
                chat_id=chat.id,
                sender_id=sender.id,
                text=random.choice(TEST_MESSAGES),
                created_at=created_at,
                is_read=bool(random.getrandbits(1)),
                client_message_id=str(uuid.uuid4())
            )
            db.add(message)
            messages.append(message)
    
    await db.commit()
    return messages


async def seed_all():
    """Заполнение базы данных тестовыми данными"""
    try:
        # Создание таблиц
        await create_tables()
        
        async with AsyncSessionLocal() as db:
            # Создание пользователей
            users = await seed_users(db)
            
            # Создание чатов
            chats = await seed_chats(db, users)
            
            # Создание сообщений
            messages = await seed_messages(db, users, chats)
            
            print(f"Создано {len(users)} пользователей")
            print(f"Создано {len(chats)} чатов")
            print(f"Создано {len(messages)} сообщений")
            
            print("\nТестовые учетные данные:")
            for user_data in TEST_USERS:
                print(f"Email: {user_data['email']}, Пароль: {user_data['password']}")
    
    except Exception as e:
        print(f"Ошибка при заполнении базы данных: {e}")


if __name__ == "__main__":
    asyncio.run(seed_all()) 