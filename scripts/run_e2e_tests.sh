#!/bin/bash
# Скрипт для запуска e2e-тестов с автоматическим запуском окружения

set -e

# Директория проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Функция для проверки зависимостей
check_dependency() {
    if ! command -v "$1" &> /dev/null; then
        echo "Ошибка: $1 не установлен"
        exit 1
    fi
}

# Проверка необходимых зависимостей
check_dependency docker
check_dependency docker-compose
check_dependency python3

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo "Создаем файл .env с тестовыми настройками..."
    cat > .env << EOL
# Тестовые настройки окружения
API_URL=http://localhost:8000
CENTRIFUGO_URL=http://localhost:8001
CENTRIFUGO_WS_URL=ws://localhost:8001/connection/websocket
TEST_USER_EMAIL=admin@example.com
TEST_USER_PASSWORD=password123
TEST_USER2_EMAIL=user1@example.com
TEST_USER2_PASSWORD=password123
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=test-secret-key-for-jwt-token
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
CENTRIFUGO_TOKEN_SECRET=test-secret-key-for-testing-only
CENTRIFUGO_API_KEY=test-api-key-for-testing-only
CENTRIFUGO_TOKEN_EXPIRE_SECONDS=3600
EOL
    echo "Файл .env создан с тестовыми настройками."
fi

# Запуск Docker-контейнеров
echo "Запуск тестового окружения..."
docker-compose -f docker-compose.yml up -d postgres redis centrifugo

# Ожидание запуска сервисов
echo "Ожидание запуска PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U postgres; do
    echo "PostgreSQL еще не готов... ожидание 1 секунда"
    sleep 1
done

echo "Ожидание запуска Redis..."
until docker-compose exec -T redis redis-cli ping | grep -q "PONG"; do
    echo "Redis еще не готов... ожидание 1 секунда"
    sleep 1
done

echo "Ожидание запуска Centrifugo..."
until curl -s http://localhost:8001/health | grep -q "ok"; do
    echo "Centrifugo еще не готов... ожидание 1 секунда"
    sleep 1
done

echo "Все сервисы запущены"

# Применение миграций
echo "Применение миграций базы данных..."
alembic upgrade head

# Создание тестовых данных
echo "Создание тестовых данных..."
python3 scripts/create_test_data.py --yes

# Запуск API сервера в фоновом режиме
echo "Запуск API сервера..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Ожидание запуска API
echo "Ожидание запуска API сервера..."
until curl -s http://localhost:8000/api/health | grep -q "ok"; do
    echo "API сервер еще не готов... ожидание 1 секунда"
    sleep 1
done

echo "API сервер запущен"

# Запуск e2e-тестов
echo "Запуск e2e-тестов..."
python3 -m pytest tests/e2e/ -v

# Сохраняем код завершения тестов
TEST_EXIT_CODE=$?

# Остановка API сервера
echo "Остановка API сервера..."
kill $API_PID

# Остановка всех контейнеров
echo "Остановка тестового окружения..."
docker-compose down

echo "Тесты завершены с кодом: $TEST_EXIT_CODE"
exit $TEST_EXIT_CODE 