# WinDI Messenger API

## Содержание

- [Аутентификация](#аутентификация)
- [Пользователи](#пользователи)
- [Чаты](#чаты)
- [Сообщения](#сообщения)
- [Centrifugo API](#centrifugo-api)
- [Присутствие и статусы](#присутствие-и-статусы)
- [Поиск](#поиск)
- [Мониторинг](#мониторинг)

## Аутентификация

### Регистрация нового пользователя

```
POST /api/v1/users/register
```

**Запрос:**
```json
{
  "email": "user@example.com",
  "username": "username",
  "password": "secure_password",
  "confirm_password": "secure_password"
}
```

**Ответ:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "username",
  "created_at": "2023-01-01T00:00:00Z",
  "is_active": true
}
```

### Авторизация пользователя

```
POST /api/v1/users/login
```

**Запрос:**
```json
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Ответ:**
```json
{
  "access_token": "jwt_token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "username"
  }
}
```

## Пользователи

### Получение профиля текущего пользователя

```
GET /api/v1/users/me
```

**Ответ:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "username",
  "created_at": "2023-01-01T00:00:00Z",
  "is_active": true
}
```

### Обновление профиля пользователя

```
PUT /api/v1/users/me
```

**Запрос:**
```json
{
  "username": "new_username",
  "bio": "About me",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

## Чаты

### Получение списка чатов

```
GET /api/v1/chats
```

**Ответ:**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Chat name",
      "is_private": false,
      "created_at": "2023-01-01T00:00:00Z",
      "last_message": {
        "id": "uuid",
        "text": "Last message text",
        "sender_id": "uuid",
        "created_at": "2023-01-01T00:01:00Z"
      },
      "unread_count": 5
    }
  ],
  "total": 10,
  "page": 1,
  "size": 20
}
```

### Создание нового чата

```
POST /api/v1/chats
```

**Запрос:**
```json
{
  "name": "New chat",
  "is_private": false,
  "participants": ["uuid1", "uuid2"]
}
```

**Ответ:**
```json
{
  "id": "uuid",
  "name": "New chat",
  "is_private": false,
  "created_at": "2023-01-01T00:00:00Z",
  "created_by": "uuid",
  "participants": [
    {
      "id": "uuid",
      "username": "username1"
    },
    {
      "id": "uuid2",
      "username": "username2"
    }
  ]
}
```

## Сообщения

### Получение истории сообщений чата

```
GET /api/v1/chats/{chat_id}/messages
```

**Параметры:**
- `limit` (integer, опционально): Количество сообщений (по умолчанию 50)
- `before_id` (string, опционально): ID сообщения, перед которым нужно получить историю
- `after_id` (string, опционально): ID сообщения, после которого нужно получить историю

**Ответ:**
```json
{
  "items": [
    {
      "id": "uuid",
      "chat_id": "uuid",
      "sender_id": "uuid",
      "text": "Message text",
      "attachments": [],
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z",
      "is_read": true,
      "client_message_id": "client123"
    }
  ],
  "total": 100,
  "has_more": true,
  "next_cursor": "next_page_token"
}
```

### Отправка сообщения (через Centrifugo API)

```
POST /api/v1/centrifugo/publish?chat_id={chat_id}
```

**Запрос:**
```json
{
  "text": "Message text",
  "attachments": [],
  "client_message_id": "client123"
}
```

**Ответ:**
```json
{
  "id": "uuid",
  "chat_id": "uuid",
  "sender_id": "uuid",
  "text": "Message text",
  "attachments": [],
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z",
  "is_read": false,
  "client_message_id": "client123"
}
```

### Отметка сообщения как прочитанного

```
POST /api/v1/messages/{message_id}/read
```

**Ответ:**
```json
{
  "id": "uuid",
  "chat_id": "uuid",
  "is_read": true,
  "updated_at": "2023-01-01T00:01:00Z"
}
```

## Centrifugo API

### Получение токена для подключения к Centrifugo

```
POST /api/v1/centrifugo/token
```

**Ответ:**
```json
{
  "token": "jwt_token_for_centrifugo"
}
```

### Прокси-маршрут для подключения к Centrifugo

```
POST /api/v1/centrifugo/connect
```

Этот маршрут используется внутренне Centrifugo и не предназначен для прямого вызова клиентами.

### Прокси-маршрут для подписки на каналы

```
POST /api/v1/centrifugo/subscribe
```

Этот маршрут используется внутренне Centrifugo и не предназначен для прямого вызова клиентами.

### Получение информации о присутствии в чате

```
GET /api/v1/centrifugo/presence/{chat_id}
```

**Ответ:**
```json
{
  "clients": {
    "client_id1": {
      "user": "user_id1",
      "user_name": "username1",
      "connected_at": 1672531200
    },
    "client_id2": {
      "user": "user_id2",
      "user_name": "username2",
      "connected_at": 1672531210
    }
  }
}
```

## Присутствие и статусы

### Отправка статуса набора текста

```
POST /api/v1/centrifugo/typing
```

**Запрос:**
```json
{
  "chat_id": "uuid",
  "is_typing": true
}
```

**Ответ:**
```json
{
  "success": true
}
```

### Получение онлайн-статуса пользователя

```
GET /api/v1/users/{user_id}/status
```

**Ответ:**
```json
{
  "is_online": true,
  "last_seen": "2023-01-01T00:00:00Z"
}
```

## Поиск

### Поиск сообщений

```
GET /api/v1/search/messages
```

**Параметры:**
- `query` (string): Поисковый запрос
- `chat_id` (string, опционально): ID чата для поиска только в одном чате
- `limit` (integer, опционально): Максимальное количество результатов (по умолчанию 20)

**Ответ:**
```json
{
  "items": [
    {
      "id": "uuid",
      "chat_id": "uuid",
      "chat_name": "Chat name",
      "sender_id": "uuid",
      "sender_name": "Username",
      "text": "Message with search <em>query</em>",
      "created_at": "2023-01-01T00:00:00Z"
    }
  ],
  "total": 5
}
```

### Поиск пользователей

```
GET /api/v1/search/users
```

**Параметры:**
- `query` (string): Поисковый запрос
- `limit` (integer, опционально): Максимальное количество результатов (по умолчанию 20)

**Ответ:**
```json
{
  "items": [
    {
      "id": "uuid",
      "username": "username",
      "email": "user@example.com",
      "avatar_url": "https://example.com/avatar.jpg",
      "is_online": true
    }
  ],
  "total": 3
}
```

## Мониторинг

### Проверка состояния API

```
GET /api/v1/health
```

**Ответ:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime": "1d 2h 3m",
  "database": "connected",
  "redis": "connected",
  "centrifugo": "connected"
}
```

### Получение информации о подключениях Centrifugo

```
GET /api/v1/centrifugo/stats
```

**Ответ:**
```json
{
  "num_clients": 100,
  "num_users": 50,
  "num_channels": 30,
  "messages_per_second": 25,
  "memory_usage_mb": 150
}
```

## Клиентские примеры

### Подключение к Centrifugo и подписка на каналы (JavaScript)

```javascript
import { Centrifuge } from 'centrifuge';

// Получение токена авторизации
const authResponse = await fetch('/api/v1/users/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'user@example.com', password: 'password' })
});
const authData = await authResponse.json();
const accessToken = authData.access_token;

// Получение токена Centrifugo
const centrifugoResponse = await fetch('/api/v1/centrifugo/token', {
  headers: { 'Authorization': `Bearer ${accessToken}` }
});
const centrifugoData = await centrifugoResponse.json();
const centrifugoToken = centrifugoData.token;

// Подключение к Centrifugo
const centrifuge = new Centrifuge('ws://localhost:8001/connection/websocket');
centrifuge.setToken(centrifugoToken);

// Подписка на канал чата
const chatSubscription = centrifuge.newSubscription('chat:123');
chatSubscription.on('publication', function(ctx) {
  console.log('Новое сообщение:', ctx.data);
});
chatSubscription.subscribe();

// Подписка на личный канал пользователя
const userSubscription = centrifuge.newSubscription(`user:${authData.user.id}`);
userSubscription.on('publication', function(ctx) {
  console.log('Личное уведомление:', ctx.data);
});
userSubscription.subscribe();

// Подключение
centrifuge.connect();

// Отправка сообщения
async function sendMessage(chatId, text) {
  const response = await fetch(`/api/v1/centrifugo/publish?chat_id=${chatId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`
    },
    body: JSON.stringify({
      text: text,
      client_message_id: `client-${Date.now()}`
    })
  });
  return await response.json();
}
``` 