# Руководство по развертыванию WinDI Messenger

В этом руководстве описывается процесс развертывания WinDI Messenger с интеграцией Centrifugo для обеспечения обмена сообщениями в реальном времени.

## Содержание

1. [Требования](#требования)
2. [Установка](#установка)
3. [Настройка окружения](#настройка-окружения)
4. [Развертывание с Docker Compose](#развертывание-с-docker-compose)
5. [Проверка развертывания](#проверка-развертывания)
6. [Настройка для производственной среды](#настройка-для-производственной-среды)
7. [Масштабирование](#масштабирование)
8. [Устранение неполадок](#устранение-неполадок)

## Требования

Для развертывания WinDI Messenger с Centrifugo требуются:

- Docker и Docker Compose
- Git
- Минимум 2 ГБ оперативной памяти
- 10 ГБ свободного места на диске

## Установка

1. Клонируйте репозиторий:

```bash
git clone https://github.com/your-organization/windi-messenger.git
cd windi-messenger
```

2. Создайте необходимые директории:

```bash
mkdir -p centrifugo/data
mkdir -p prometheus/data
mkdir -p logs
mkdir -p media
```

## Настройка окружения

1. Создайте файл `.env` на основе примера:

```bash
cp .env.example .env
```

2. Отредактируйте файл `.env`, указав безопасные значения:

```ini
# Обязательно измените эти значения для безопасности
SECRET_KEY=generate-a-secure-random-string
CENTRIFUGO_TOKEN_SECRET=generate-a-secure-random-string
CENTRIFUGO_API_KEY=generate-a-secure-random-string
CENTRIFUGO_ADMIN_PASSWORD=secure-admin-password
CENTRIFUGO_ADMIN_SECRET=secure-admin-secret

# Настройте другие параметры при необходимости
ENVIRONMENT=production
DEBUG=false
```

Для генерации безопасных случайных строк можно использовать:

```bash
openssl rand -hex 32
```

3. Убедитесь, что в файле `centrifugo/config.json` нет секретных значений - они должны передаваться через переменные окружения.

## Развертывание с Docker Compose

1. Запустите систему:

```bash
docker-compose up -d
```

2. Проверьте, что все контейнеры запущены и работают:

```bash
docker-compose ps
```

Все контейнеры должны иметь статус `Up`.

3. Создайте миграции базы данных:

```bash
docker-compose exec api alembic upgrade head
```

4. Создайте тестовых пользователей (опционально):

```bash
docker-compose exec api python scripts/create_test_data.py --force
```

## Проверка развертывания

1. Проверьте доступность API сервера:

```bash
curl http://localhost:8000/health
```

Ответ должен быть `{"status":"ok","version":"1.0.0"}`.

2. Проверьте доступность Centrifugo:

```bash
curl http://localhost:8001/health
```

Ответ должен быть `{"status":"available"}`.

3. Выполните скрипт проверки интеграции:

```bash
docker-compose exec api python scripts/test_centrifugo_integration.py
```

4. Проверьте административный интерфейс Centrifugo:

Откройте в браузере `http://localhost:8002` и войдите с учетными данными администратора (указанными в `.env`).

## Настройка для производственной среды

### SSL/TLS

Для безопасного развертывания в производственной среде необходимо настроить SSL/TLS. Рекомендуется использовать обратный прокси, такой как Nginx или Traefik:

1. Добавьте в `docker-compose.yml` сервис Nginx:

```yaml
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/conf.d:/etc/nginx/conf.d
      - ./nginx/ssl:/etc/nginx/ssl
      - ./nginx/www:/var/www/html
    depends_on:
      - api
      - centrifugo
```

2. Настройте HTTPS в Nginx для API и Centrifugo.

3. Обновите значения в `.env`:

```ini
# Обновите URL для HTTPS
CENTRIFUGO_URL=https://centrifugo.yourdomain.com
CORS_ORIGINS=https://yourdomain.com
```

### Постоянное хранение данных

Убедитесь, что для всех томов Docker настроено постоянное хранение:

```yaml
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      device: /path/to/permanent/storage/postgres
      o: bind
  redis_data:
    driver: local
    driver_opts:
      type: none
      device: /path/to/permanent/storage/redis
      o: bind
  # ... и так далее для других томов
```

### Ротация логов

Настройте ротацию логов для предотвращения переполнения диска:

```bash
cat > /etc/logrotate.d/windi-messenger << EOF
/path/to/windi-messenger/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
}
EOF
```

## Масштабирование

WinDI Messenger с Centrifugo можно масштабировать горизонтально для обработки большего количества пользователей:

### Масштабирование API сервера

```yaml
  api:
    deploy:
      replicas: 3
```

### Масштабирование Centrifugo

Centrifugo поддерживает горизонтальное масштабирование с использованием Redis в качестве брокера. При запуске нескольких узлов:

```yaml
  centrifugo:
    deploy:
      replicas: 3
    command: centrifugo --config=/centrifugo/config.json --engine=redis --address=redis://redis:6379/0
```

### Масштабирование базы данных

Для масштабирования базы данных рекомендуется настроить репликацию PostgreSQL:

1. Настройте мастер и реплики PostgreSQL.
2. Используйте решение для балансировки нагрузки, например, PgBouncer.

## Устранение неполадок

### Проблемы с подключением к Centrifugo

1. **Ошибка подключения WebSocket**

   Проверьте доступность Centrifugo:
   
   ```bash
   curl http://localhost:8001/health
   ```
   
   Проверьте логи Centrifugo:
   
   ```bash
   docker-compose logs centrifugo
   ```

2. **Ошибка авторизации**

   Убедитесь, что переменные окружения правильно настроены:
   
   ```bash
   docker-compose exec centrifugo env | grep CENTRIFUGO
   ```
   
   Проверьте маршрут получения токена:
   
   ```bash
   curl -X POST http://localhost:8000/api/v1/centrifugo/token -H "Authorization: Bearer YOUR_JWT_TOKEN"
   ```

3. **Не доставляются сообщения**

   Проверьте логи API:
   
   ```bash
   docker-compose logs api
   ```
   
   Проверьте, что сообщения публикуются в правильный канал:
   
   ```bash
   docker-compose exec api python -c "from app.core.centrifugo import centrifugo_client; print(centrifugo_client.get_chat_channel_name(1))"
   ```

### Сбор диагностической информации

Для сбора всей диагностической информации выполните:

```bash
# Сохраняем информацию о контейнерах
docker-compose ps > diagnostics.txt

# Добавляем логи каждого сервиса
for service in api db redis centrifugo prometheus; do
  echo "=== Logs for $service ===" >> diagnostics.txt
  docker-compose logs --tail=100 $service >> diagnostics.txt
done

# Проверяем переменные окружения
docker-compose config >> diagnostics.txt

# Проверяем сетевые соединения
docker network inspect windi-messenger_default >> diagnostics.txt
```

### Часто задаваемые вопросы

**В: Получаю ошибку "dial tcp 127.0.0.1:8001: connect: connection refused" при попытке подключиться к Centrifugo из API.**

О: Убедитесь, что в `.env` указан правильный URL для Centrifugo внутри Docker сети. Должно быть `CENTRIFUGO_URL=http://centrifugo:8000`, а не localhost.

**В: Как посмотреть текущие подключения к Centrifugo?**

О: В административном интерфейсе Centrifugo (http://localhost:8002) перейдите в раздел "Nodes" для просмотра статистики.

**В: Как изменить время хранения истории сообщений?**

О: Настройте параметры `history_ttl` и `history_size` в `centrifugo/config.json` для нужного канала или всего сервера. 