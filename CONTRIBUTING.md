# Руководство по внесению вклада в WinDI Messenger

Спасибо за интерес к улучшению WinDI Messenger! Это руководство поможет вам настроить среду разработки и внести вклад в проект.

## Настройка среды разработки

### Предварительные требования

- Python 3.10+
- Docker и Docker Compose
- Git

### Локальная настройка

1. Форкните репозиторий на GitHub.

2. Клонируйте ваш форк:
   ```bash
   git clone https://github.com/your-username/windi-messenger.git
   cd windi-messenger
   ```

3. Создайте виртуальное окружение:
   ```bash
   python -m venv venv
   source venv/bin/activate  # На Windows: venv\Scripts\activate
   ```

4. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements.dev.txt  # Зависимости для разработки
   ```

5. Запустите контейнеры:
   ```bash
   docker-compose up -d
   ```

## Процесс разработки

### Создание новой функциональности

1. Создайте новую ветку:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Внесите изменения в код.

3. Запустите тесты:
   ```bash
   pytest
   ```

4. Отправьте изменения:
   ```bash
   git add .
   git commit -m "Add: описание вашей функциональности"
   git push origin feature/your-feature-name
   ```

5. Создайте Pull Request на GitHub.

## Работа с Centrifugo

При разработке функционала, связанного с сообщениями в реальном времени, используйте Centrifugo API:

### Правила использования Centrifugo

1. **Не используйте напрямую WebSocket API FastAPI**:
   ```python
   # Неправильно - не используйте
   from fastapi import WebSocket

   @app.websocket("/ws")
   async def websocket_endpoint(websocket: WebSocket):
       ...
   ```

2. **Вместо этого используйте Centrifugo API**:
   ```python
   # Правильно
   from app.core.centrifugo import centrifugo_client
   
   async def publish_message(channel: str, data: dict):
       await centrifugo_client.publish(channel, data)
   ```

3. **Для получения клиентского кода используйте CentrifugoManager**:
   ```python
   from app.utils.centrifugo_manager import centrifugo_manager
   
   # Применяйте методы менеджера для работы с каналами
   centrifugo_manager.join_chat(chat_id, user_id)
   ```

### Тестирование работы с Centrifugo

Используйте встроенные скрипты для тестирования интеграции:

```bash
python scripts/test_centrifugo_integration.py
```

## Стиль кода

### Python

- Следуйте PEP 8
- Используйте аннотации типов
- Пишите докстринги для всех публичных функций и классов
- Именуйте переменные и функции в snake_case
- Именуйте классы в CamelCase

### JavaScript/TypeScript

- Следуйте ESLint конфигурации проекта
- Используйте async/await вместо колбеков
- Используйте современный синтаксис ES6+

## Документация

При добавлении новой функциональности обязательно обновляйте документацию:

1. Обновите соответствующие файлы в директории `docs/`
2. Добавьте описание API в комментарии OpenAPI/Swagger
3. Обновите README.md при необходимости

## Коммиты

Используйте префиксы для коммитов:

- `Add:` - добавление новой функциональности
- `Fix:` - исправление ошибок
- `Update:` - обновление существующей функциональности
- `Refactor:` - рефакторинг кода
- `Docs:` - обновление документации
- `Test:` - добавление или обновление тестов
- `Chore:` - настройка проекта, зависимости и т.д.

## Код-ревью

Каждый Pull Request должен пройти проверку кода. Будьте готовы к обсуждению и внесению изменений.

## Создание релизов

Релизы создаются автоматически из ветки `main` с помощью GitHub Actions.

## Благодарим вас за вклад в WinDI Messenger! 