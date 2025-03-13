# Репозитории базы данных

Это директория содержит репозитории для работы с базой данных в приложении WinDI Messenger.

## Структура

- `__init__.py` - экспортирует все репозитории для удобного импорта
- `base.py` - базовый класс репозитория с общими методами
- `user.py` - репозиторий для работы с пользователями
- `chat.py` - репозиторий для работы с чатами
- `message.py` - репозиторий для работы с сообщениями

## Использование

Импортируйте репозитории из пакета `app.db.repositories`:

```python
from app.db.repositories import UserRepository, ChatRepository, MessageRepository
```

Инициализируйте репозиторий с сессией базы данных:

```python
user_repo = UserRepository(db_session)
chat_repo = ChatRepository(db_session)
message_repo = MessageRepository(db_session)
```

Используйте методы репозитория для работы с данными:

```python
# Пример получения пользователя по email
user = await user_repo.get_by_email("user@example.com")

# Пример создания группового чата
chat = await chat_repo.create_group_chat(
    name="Тестовый чат",
    creator_id=user_id,
    user_ids=[user1_id, user2_id]
)

# Пример получения сообщений чата
messages = await message_repo.get_chat_messages(chat_id, limit=50, offset=0)
``` 