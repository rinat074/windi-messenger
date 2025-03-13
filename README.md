# WinDI Messenger

Современный мессенджер с использованием FastAPI, PostgreSQL, Redis и Centrifugo для коммуникации в реальном времени.

## Технологический стек

- **Backend**: FastAPI (Python)
- **База данных**: PostgreSQL
- **Кэш и брокер сообщений**: Redis
- **Коммуникация в реальном времени**: Centrifugo
- **Контейнеризация**: Docker и Docker Compose
- **Мониторинг**: Prometheus

## Архитектура

WinDI Messenger использует микросервисную архитектуру:

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

### Ключевые компоненты

- **API Сервер (FastAPI)**: Обрабатывает HTTP запросы, управляет чатами и сообщениями
- **Centrifugo**: Обеспечивает обмен сообщениями в реальном времени
- **PostgreSQL**: Хранит данные пользователей, чатов и сообщений
- **Redis**: Используется как кэш и брокер для Centrifugo

## Установка и запуск

### Предварительные требования

- Docker и Docker Compose
- Git

### Установка

1. Клонировать репозиторий:
   ```bash
   git clone https://github.com/rinat074/windi-messenger.git
   cd windi-messenger
   ```

2. Создать файл окружения:
   ```bash
   cp .env.example .env
   ```

3. Отредактировать `.env` с нужными параметрами

### Запуск

1. Запустить контейнеры:
   ```bash
   docker-compose up -d
   ```

2. Применить миграции:
   ```bash
   docker-compose exec api alembic upgrade head
   ```

3. Создать тестовые данные (опционально):
   ```bash
   docker-compose exec api python scripts/create_test_data.py
   ```

## Документация API

API документация доступна по адресу:
```
http://localhost:8000/docs
```

## Работа с Centrifugo

### Обзор

WinDI Messenger использует Centrifugo для коммуникации в реальном времени. Ранее проект использовал встроенный WebSocket функционал FastAPI, но мы перешли на Centrifugo для улучшения масштабируемости и производительности.

### Подключение к Centrifugo

Для подключения к Centrifugo сначала необходимо получить токен:

```javascript
// Получение токена
const response = await fetch('/api/v1/centrifugo/token', {
  headers: { 'Authorization': `Bearer ${accessToken}` }
});
const { token } = await response.json();

// Подключение к Centrifugo
const centrifuge = new Centrifuge('ws://localhost:8001/connection/websocket');
centrifuge.setToken(token);
centrifuge.connect();
```

### Подписка на каналы

```javascript
// Подписка на канал чата
const subscription = centrifuge.newSubscription(`chat:${chatId}`);

// Обработка входящих сообщений
subscription.on('publication', function(ctx) {
  const message = ctx.data;
  console.log('Новое сообщение:', message);
});

// Активация подписки
subscription.subscribe();
```

### Отправка сообщений

```javascript
// Отправка сообщения через API
const sendMessage = async (chatId, text) => {
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
};
```

## Мониторинг

### Проверка состояния

```bash
# Проверка API
curl http://localhost:8000/health

# Проверка Centrifugo
curl http://localhost:8001/health
```

### Мониторинг Centrifugo

Для мониторинга Centrifugo можно использовать встроенный скрипт:

```bash
python scripts/monitor_centrifugo.py --duration 60
```

### Административный интерфейс Centrifugo

Административный интерфейс Centrifugo доступен по адресу:
```
http://localhost:8002
```

## Тестирование

### Интеграционное тестирование

```bash
python scripts/test_centrifugo_integration.py
```

### Создание тестовых данных

```bash
python scripts/create_test_data.py
```

## Дополнительная документация

Подробная документация доступна в директории `docs/`:

- [Руководство по развертыванию](docs/DEPLOYMENT.md)
- [Руководство разработчика по Centrifugo](docs/CENTRIFUGO_DEV_GUIDE.md)
- [Миграция с WebSocket на Centrifugo](docs/WEBSOCKET_TO_CENTRIFUGO.md)

## Вклад в проект

Мы приветствуем вклад в развитие проекта. Пожалуйста, ознакомьтесь с [руководством по внесению вклада](CONTRIBUTING.md).

# WinDI Messenger - Тестирование

## Структура тестов

Проект содержит различные типы тестов, разделенные по категориям:

- `tests/unit/` - Модульные тесты отдельных компонентов
- `tests/integration/` - Интеграционные тесты взаимодействия компонентов
- `tests/e2e/` - Сквозные тесты полных пользовательских сценариев
- `tests/performance/` - Тесты производительности и нагрузки
- `tests/conftest.py` - Общие фикстуры и настройки pytest

## Запуск тестов

Для удобного запуска тестов используйте скрипт `scripts/run_tests.py`:

```bash
# Запуск модульных тестов
python scripts/run_tests.py unit

# Запуск интеграционных тестов с подробным выводом
python scripts/run_tests.py integration -v

# Запуск сквозных тестов с отчетом о покрытии кода
python scripts/run_tests.py e2e -c

# Запуск нагрузочных тестов
python scripts/run_tests.py performance

# Запуск нагрузочных тестов в полном режиме
python scripts/run_tests.py performance -f

# Запуск всех тестов с остановкой при первой ошибке
python scripts/run_tests.py all -x

# Запуск конкретного теста
python scripts/run_tests.py tests/unit/core/test_centrifugo_sample.py
```

## Конфигурация окружения

Для запуска тестов необходимо наличие `.env` файла с конфигурацией. Если его нет, скрипт `run_tests.py` создаст файл с тестовыми настройками. Для запуска интеграционных и e2e тестов требуется запущенное приложение и его зависимости.

## Маркеры тестов

В проекте используются следующие маркеры:

- `unit` - модульные тесты
- `integration` - интеграционные тесты
- `e2e` - сквозные тесты
- `performance` - тесты производительности
- `slow` - медленные тесты
- `centrifugo` - тесты, связанные с Centrifugo

## Фикстуры

В проекте определены различные фикстуры для тестирования:

### Общие фикстуры (`tests/conftest.py`)

- `event_loop` - создает новый event loop для каждого теста
- `auth_headers` - получает заголовки авторизации
- `auth_token` - получает токен авторизации
- `centrifugo_token` - получает токен Centrifugo
- `mock_centrifugo_client` - мок для клиента Centrifugo
- `test_chat_id` - создает тестовый чат
- `test_message_data` - генерирует тестовые данные

### Фикстуры модульных тестов (`tests/unit/conftest.py`)

- `mock_centrifugo_client_unit` - расширенный мок для модульных тестов
- `mock_httpx_client` - мок для HTTP-клиента
- `test_centrifugo_client` - тестовый экземпляр CentrifugoClient
- `test_centrifugo_manager` - тестовый экземпляр CentrifugoManager

### Фикстуры интеграционных тестов (`tests/integration/conftest.py`)

- `create_test_message` - создает тестовое сообщение в чате
- `get_message_history` - получает историю сообщений чата
- `check_centrifugo_presence` - проверяет присутствие пользователей в канале

### Фикстуры нагрузочных тестов (`tests/performance/conftest.py`)

- `performance_config` - конфигурация для нагрузочных тестов
- `performance_result_handler` - обработчик результатов
- `test_user_credentials` - учетные данные тестового пользователя
- `test_auth_token` - токен авторизации для тестов
- `test_performance_chat` - тестовый чат для нагрузочных тестов

## CI/CD интеграция

Проект настроен для автоматического запуска тестов в CI/CD с использованием GitHub Actions. Конфигурация находится в файле `.github/workflows/tests.yml`.

## Отчеты о тестировании

При запуске тестов с флагом `-c` (coverage) генерируется отчет о покрытии кода в HTML формате, который доступен в директории `htmlcov/`.

## Требования для запуска тестов

Все необходимые зависимости для тестирования перечислены в файле `requirements.dev.txt`. Установите их с помощью pip:

```bash
pip install -r requirements.dev.txt
``` 