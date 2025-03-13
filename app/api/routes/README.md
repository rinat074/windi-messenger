# API маршруты WinDI Messenger

Эта директория содержит маршруты API для приложения WinDI Messenger. Приложение предоставляет как REST API для стандартных операций, так и интеграцию с Centrifugo для обмена сообщениями в реальном времени.

## Структура

```
routes/
├── __init__.py               # Основной файл маршрутизации
├── user_routes.py            # Маршруты для пользователей
├── history_routes.py         # Маршруты для истории сообщений
├── centrifugo/               # Маршруты для интеграции с Centrifugo
│   ├── __init__.py
│   ├── centrifugo_routes.py  # Маршруты для работы с Centrifugo API
│   └── centrifugo_utils.py   # Утилиты для работы с Centrifugo
└── chat/                     # Маршруты для работы с чатами
    ├── __init__.py
    └── chat_routes.py        # REST API для чатов
```

## Основные компоненты

### REST API

REST API используется для традиционных операций: управление пользователями, чатами, получение истории сообщений, и т.д.

### Centrifugo API

Centrifugo API обеспечивает обмен сообщениями в реальном времени, заменив ранее используемый WebSocket. Это позволяет более эффективно масштабировать приложение и улучшить надежность коммуникации.

## Примеры API endpoints

### Пользователи

- `POST /api/v1/users/register` - Регистрация нового пользователя
- `POST /api/v1/users/login` - Авторизация пользователя (получение токена)
- `GET /api/v1/users/me` - Получение данных текущего пользователя
- `PUT /api/v1/users/me` - Обновление данных пользователя

### Чаты

- `GET /api/v1/chats` - Получение списка чатов пользователя
- `POST /api/v1/chats` - Создание нового чата
- `GET /api/v1/chats/{chat_id}` - Получение информации о чате
- `PUT /api/v1/chats/{chat_id}` - Обновление информации о чате
- `DELETE /api/v1/chats/{chat_id}` - Удаление чата
- `GET /api/v1/chats/{chat_id}/messages` - Получение сообщений чата
- `GET /api/v1/chats/{chat_id}/members` - Получение участников чата
- `POST /api/v1/chats/{chat_id}/members` - Добавление участника в чат

### История сообщений

- `GET /api/v1/history` - Получение истории сообщений с фильтрацией
- `GET /api/v1/history/search` - Поиск по истории сообщений

### Centrifugo

- `POST /api/v1/centrifugo/token` - Получение токена для подключения к Centrifugo
- `POST /api/v1/centrifugo/subscribe/{channel}` - Получение токена подписки на канал
- `POST /api/v1/centrifugo/publish` - Публикация сообщения через Centrifugo
- `GET /api/v1/centrifugo/presence/{chat_id}` - Получение присутствующих пользователей в чате
- `GET /api/v1/centrifugo/history/{chat_id}` - Получение истории сообщений из Centrifugo

## Использование Centrifugo

### Подключение к Centrifugo

Для подключения к Centrifugo необходимо:

1. Получить токен подключения:
```
POST /api/v1/centrifugo/token
```

2. Использовать полученный токен для инициализации соединения:
```javascript
const centrifuge = new Centrifuge('ws://localhost:8001/connection/websocket');
centrifuge.setToken(token);
centrifuge.connect();
```

### Подписка на канал чата

```javascript
const subscription = centrifuge.newSubscription(`chat:${chatId}`);
subscription.on('publication', function(ctx) {
    // Обработка входящего сообщения
    console.log('Новое сообщение:', ctx.data);
});
subscription.subscribe();
```

### Отправка сообщения

```javascript
// Через REST API
const response = await fetch(`/api/v1/centrifugo/publish?chat_id=${chatId}`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
        text: 'Привет мир!',
        client_message_id: `client-${Date.now()}`
    })
});
```

## Авторизация

Все маршруты API (кроме /login и /register) требуют авторизации через JWT токен, который передается в заголовке Authorization:

```
Authorization: Bearer <token>
```

## Версионирование API

API используется с префиксом `/api/v1/`, что позволяет в будущем вводить новые версии API без нарушения обратной совместимости.

## Документация API

Полная документация API доступна по адресу `/docs` при запущенном сервере (Swagger UI). 