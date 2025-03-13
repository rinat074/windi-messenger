# Модели базы данных

Это директория содержит модели базы данных, используемые в приложении WinDI Messenger.

## Структура

- `__init__.py` - экспортирует все модели для удобного импорта
- `user.py` - модель пользователя (User)
- `chat.py` - модель чата (Chat) и таблица связи пользователей с чатами (user_chat)
- `message.py` - модель сообщения (Message)

## Использование

Импортируйте модели из пакета `app.db.models`:

```python
from app.db.models import User, Chat, Message
```

или более специфично:

```python
from app.db.models.user import User
from app.db.models.chat import Chat, ChatType
from app.db.models.message import Message
``` 