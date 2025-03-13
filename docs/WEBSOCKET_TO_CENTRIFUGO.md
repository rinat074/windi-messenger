# Переход с FastAPI WebSocket на Centrifugo

Этот документ объясняет процесс миграции с встроенного механизма WebSocket в FastAPI на Centrifugo - мощный сервер коммуникации в реальном времени.

## Сделанные изменения

1. **Удалены модули WebSocket:**
   - Удалена директория `app/api/ws/` с WebSocket-маршрутами
   - Удален класс `WebSocketMessage` из схем сообщений

2. **Настроен Centrifugo:**
   - Добавлен сервис Centrifugo в `docker-compose.yml`
   - Создан файл конфигурации `centrifugo/config.json`
   - Добавлены настройки Centrifugo в `app/core/config.py`

3. **Созданы новые компоненты:**
   - Создан клиент Centrifugo в `app/core/centrifugo.py`
   - Создан менеджер Centrifugo в `app/utils/centrifugo_manager.py`
   - Добавлены маршруты для интеграции с Centrifugo в `app/api/routes/centrifugo_routes.py`

4. **Обновлены существующие компоненты:**
   - Обновлен `app/core/session.py` для использования Centrifugo вместо WebSocket
   - Обновлен `app/services/message_service.py` для отправки сообщений через Centrifugo
   - Обновлен `app/api/routes/__init__.py` для удаления WebSocket-маршрутов и добавления маршрутов Centrifugo

## Импорты и зависимости


## Отправка сообщений

### Старый способ (WebSocket):

```python
await manager.broadcast_to_chat({
    "event": "message",
    "data": message.dict()
}, chat_id)
```

### Новый способ (Centrifugo):

```python
chat_channel = centrifugo_client.get_chat_channel_name(str(chat_id))
await centrifugo_client.publish(chat_channel, {
    "event": "message",
    "data": message.dict()
})
```

## Клиентская сторона

### Старый способ (WebSocket):

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/${chatId}?token=${accessToken}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Обработка сообщения
};
```

### Новый способ (Centrifugo):

```javascript
import { Centrifuge } from 'centrifuge';

// Получение токена
const response = await fetch('/api/v1/centrifugo/token', {
  headers: { 'Authorization': `Bearer ${accessToken}` }
});
const { token } = await response.json();

// Подключение к Centrifugo
const centrifuge = new Centrifuge('ws://localhost:8001/connection/websocket');
centrifuge.setToken(token);

// Подписка на канал чата
const sub = centrifuge.newSubscription(`chat:${chatId}`);
sub.on('publication', (ctx) => {
  const data = ctx.data;
  // Обработка сообщения
});

sub.subscribe();
centrifuge.connect();
```

## Преимущества перехода

1. **Масштабирование:** Centrifugo можно масштабировать горизонтально для обработки большого количества соединений
2. **Отслеживание присутствия:** Встроенная поддержка функции presence для отслеживания пользователей в каналах
3. **История сообщений:** Встроенная поддержка хранения истории сообщений
4. **Администрирование:** Удобная административная панель для мониторинга и управления
5. **Улучшенная надежность:** Reconnect с восстановлением состояния, поддержка различных транспортов 