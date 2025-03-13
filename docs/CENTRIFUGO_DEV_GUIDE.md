# Руководство разработчика по интеграции с Centrifugo

Данный документ описывает архитектуру и принципы работы с Centrifugo в проекте WinDI Messenger для разработчиков.

## Содержание

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Структура каналов](#структура-каналов)
3. [Авторизация и токены](#авторизация-и-токены)
4. [Отправка сообщений](#отправка-сообщений)
5. [Получение сообщений](#получение-сообщений)
6. [Работа с присутствием и статусами](#работа-с-присутствием-и-статусами)
7. [Дополнительные возможности](#дополнительные-возможности)
8. [Отладка и профилирование](#отладка-и-профилирование)

## Обзор архитектуры

WinDI Messenger использует Centrifugo в качестве брокера сообщений реального времени. Общая архитектура:

```
┌─────────┐         ┌───────────┐         ┌─────────────┐
│ Клиент  │◄───WS───┤ Centrifugo │◄───API──┤ API Сервер  │
└─────────┘         └───────────┘         └─────────────┘
                          │                      │
                          │                      │
                          ▼                      ▼
                     ┌─────────┐           ┌─────────┐
                     │  Redis  │           │ Postgres│
                     └─────────┘           └─────────┘
```

### Ключевые компоненты:

1. **API Сервер (FastAPI)**: Обрабатывает HTTP запросы, аутентифицирует пользователей, управляет чатами и проверяет права доступа.

2. **Centrifugo**: Обрабатывает WebSocket-соединения, маршрутизирует сообщения между клиентами, управляет присутствием и историей.

3. **Redis**: Хранит состояние Centrifugo, обеспечивая горизонтальное масштабирование и сохранение данных о подписках и присутствии.

4. **PostgreSQL**: Хранит постоянные данные о пользователях, чатах и сообщениях.

## Структура каналов

Каналы Centrifugo используются для группировки сообщений и управления подписками. В WinDI Messenger используются следующие типы каналов:

### Каналы чатов
```
chat:{chat_id}
```
Все сообщения, связанные с конкретным чатом, публикуются в соответствующий канал чата. Например, `chat:1` для чата с ID 1.

### Персональные каналы пользователей
```
user:{user_id}
```
Используются для отправки персональных уведомлений пользователю, таких как новые запросы в друзья, системные сообщения и т.д. Например, `user:42` для пользователя с ID 42.

### Служебные каналы
```
system:notifications
```
Для системных оповещений всем пользователям (обслуживание, обновления и т.д.).

## Авторизация и токены

Centrifugo использует JWT-токены для аутентификации клиентов:

### Получение токена

```python
# Серверная часть (Python)
from app.core.centrifugo import centrifugo_client

# Генерация JWT токена для подключения
token = centrifugo_client.generate_connection_token(
    user_id=str(user.id),
    user_name=user.username
)
```

```javascript
// Клиентская часть (JavaScript)
// Сначала получаем токен с сервера
async function getToken() {
  const response = await fetch('/api/v1/centrifugo/token', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${authToken}` }
  });
  const data = await response.json();
  return data.token;
}
```

### Подключение с токеном

```javascript
import { Centrifuge } from 'centrifuge';

// Получаем токен и подключаемся
const token = await getToken();
const centrifuge = new Centrifuge('ws://localhost:8001/connection/websocket');
centrifuge.setToken(token);
centrifuge.connect();
```

### Проверка доступа к каналам

Доступ к каналам проверяется через прокси-эндпоинты, настроенные в конфигурации Centrifugo:

```json
{
  "proxy_connect_endpoint": "http://api:8000/api/v1/centrifugo/connect",
  "proxy_subscribe_endpoint": "http://api:8000/api/v1/centrifugo/subscribe"
}
```

В маршруте `centrifugo_subscribe_proxy` проверяется доступ пользователя к каналу:

```python
@router.post("/subscribe")
async def centrifugo_subscribe_proxy(body: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    # Получаем данные из запроса
    user_id = body.get("user", {}).get("user_id")
    channel = body.get("channel")
    
    # Проверяем доступ к каналу
    if channel.startswith("chat:"):
        chat_id = channel.split(":", 1)[1]
        has_access = await check_chat_access(db, user_id, chat_id)
        
        if not has_access:
            return {"status": 403}  # Запрещаем доступ
    
    return {"status": 200}  # Разрешаем доступ
```

## Отправка сообщений

### Через API (рекомендуемый подход)

Для отправки сообщений через API используйте маршрут `/centrifugo/publish`:

```python
# Серверная часть (Python)
@router.post("/publish")
async def publish_message(
    chat_id: int,
    message: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Проверка прав доступа к чату
    is_member = await is_user_in_chat(db, current_user.id, chat_id)
    if not is_member:
        raise HTTPException(status_code=403)
    
    # Сохранение сообщения в БД
    new_message = await create_message(db, message)
    
    # Публикация через Centrifugo
    channel = centrifugo_client.get_chat_channel_name(chat_id)
    centrifugo_message = centrifugo_client.format_message_for_centrifugo(new_message)
    await centrifugo_client.publish(channel, centrifugo_message)
    
    return new_message
```

```javascript
// Клиентская часть (JavaScript)
async function sendMessage(chatId, text) {
  const response = await fetch(`/api/v1/centrifugo/publish?chat_id=${chatId}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${authToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      content: text,
      attachments: []
    })
  });
  
  return await response.json();
}
```

### Напрямую через Centrifugo API (для продвинутых случаев)

```python
# Серверная часть (Python)
await centrifugo_client.publish(
    channel=f"chat:{chat_id}",
    data={
        "type": "message",
        "content": "Текст сообщения",
        "sender_id": user_id,
        "timestamp": int(time.time())
    }
)
```

```javascript
// Клиентская часть (JavaScript)
// Обратите внимание, что необходимо настроить разрешения в Centrifugo
// для публикации напрямую с клиента
centrifuge.publish("chat:1", {
  type: "message",
  content: "Текст сообщения",
  sender_id: "123",
  timestamp: Math.floor(Date.now() / 1000)
});
```

## Получение сообщений

### Подписка на канал и обработка сообщений

```javascript
// Клиентская часть (JavaScript)
const subscription = centrifuge.newSubscription('chat:1');

// Обработка входящих сообщений
subscription.on('publication', function(ctx) {
  const message = ctx.data;
  console.log('Новое сообщение:', message);
  // Обработка сообщения...
});

// События присоединения/отсоединения пользователей
subscription.on('join', function(ctx) {
  console.log('Пользователь присоединился:', ctx.info);
});

subscription.on('leave', function(ctx) {
  console.log('Пользователь покинул чат:', ctx.info);
});

// Активация подписки
subscription.subscribe();
```

### Получение истории сообщений

```javascript
// Клиентская часть (JavaScript)
// Получение истории через Centrifugo
subscription.history().then(function(response) {
  const messages = response.publications;
  console.log('История сообщений:', messages);
});

// Либо через REST API
async function getChatHistory(chatId) {
  const response = await fetch(`/api/v1/history/${chatId}`, {
    headers: { 'Authorization': `Bearer ${authToken}` }
  });
  return await response.json();
}
```

## Работа с присутствием и статусами

### Отслеживание присутствия

```javascript
// Клиентская часть (JavaScript)
// Получение информации о присутствии через Centrifugo
subscription.presence().then(function(response) {
  const clients = response.presence;
  console.log('Пользователи онлайн:', clients);
});

// Либо через REST API
async function getPresence(chatId) {
  const response = await fetch(`/api/v1/centrifugo/presence/${chatId}`, {
    headers: { 'Authorization': `Bearer ${authToken}` }
  });
  return await response.json();
}
```

### Отправка статусов активности

```javascript
// Клиентская часть (JavaScript)
function sendTypingStatus(chatId, isTyping) {
  fetch(`/api/v1/centrifugo/publish`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${authToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      channel: `chat:${chatId}`,
      data: {
        type: 'typing',
        user_id: currentUserId,
        user_name: currentUserName,
        is_typing: isTyping,
        timestamp: Math.floor(Date.now() / 1000)
      }
    })
  });
}
```

## Дополнительные возможности

### Отслеживание состояния соединения

```javascript
// Клиентская часть (JavaScript)
centrifuge.on('connecting', function(ctx) {
  console.log(`Подключение... (попытка #${ctx.attempt})`);
});

centrifuge.on('connected', function(ctx) {
  console.log('Подключено!', ctx);
});

centrifuge.on('disconnected', function(ctx) {
  console.log('Отключено:', ctx);
});
```

### Работа с несколькими подписками

```javascript
// Клиентская часть (JavaScript)
// Подписка на персональный канал пользователя
const userChannel = centrifuge.newSubscription(`user:${userId}`);
userChannel.on('publication', function(ctx) {
  const notification = ctx.data;
  console.log('Новое уведомление:', notification);
});
userChannel.subscribe();

// Подписка на канал чата
const chatChannel = centrifuge.newSubscription(`chat:${chatId}`);
chatChannel.on('publication', function(ctx) {
  const message = ctx.data;
  console.log('Новое сообщение:', message);
});
chatChannel.subscribe();
```

### Вспомогательные функции на сервере

Класс `CentrifugoClient` в `app/core/centrifugo.py` предоставляет множество полезных методов:

```python
# Получение имени канала для чата
channel = centrifugo_client.get_chat_channel_name(chat_id)

# Получение имени канала для пользователя
channel = centrifugo_client.get_user_channel_name(user_id)

# Публикация в несколько каналов
await centrifugo_client.broadcast(
    channels=["chat:1", "chat:2"],
    data={"type": "system", "content": "Системное сообщение"}
)

# Форматирование данных сообщения
message_data = centrifugo_client.format_message_for_centrifugo(message)
```

## Отладка и профилирование

### Включение отладочного режима

В настройках Centrifugo:

```json
{
  "debug": true
}
```

В переменных окружения:

```
CENTRIFUGO_DEBUG=true
```

### Мониторинг на административной панели

Административная панель доступна по адресу `http://localhost:8002/`. Здесь вы можете:

- Просматривать текущие подключения
- Отслеживать статистику каналов
- Публиковать тестовые сообщения
- Просматривать историю и присутствие в каналах

### Советы по отладке

1. **Используйте административную панель Centrifugo** для просмотра активных подключений и каналов.

2. **Логирование WebSocket-трафика**:
   ```javascript
   centrifuge.setLogLevel(3); // Подробное логирование
   ```

3. **Проверка правильности JWT токенов**:
   ```python
   import jwt
   token = "your_token_here"
   decoded = jwt.decode(token, verify=False)
   print(decoded)
   ```

4. **Тестирование публикации через curl**:
   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -H "Authorization: apikey your_api_key" \
     -d '{"method":"publish","params":{"channel":"chat:1","data":{"text":"test"}}}' \
     http://localhost:8001/api
   ```

5. **Запуск диагностического скрипта**:
   ```bash
   python scripts/test_centrifugo_integration.py
   ```

### Распространенные проблемы и решения

1. **Ошибка "unauthorized"**:
   - Проверьте, правильно ли настроен секретный ключ для JWT
   - Убедитесь, что токен не просрочен
   - Проверьте алгоритм подписи (по умолчанию HS256)

2. **Ошибка "permission denied"**:
   - Проверьте прокси-эндпоинты для проверки прав доступа
   - Проверьте правильность формата канала
   - Проверьте настройки namespaces в конфигурации Centrifugo

3. **Сообщения не доставляются**:
   - Проверьте правильность имен каналов
   - Проверьте успешность публикации на сервере
   - Проверьте подписку клиента на правильный канал 