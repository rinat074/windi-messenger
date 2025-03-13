#!/usr/bin/env python
"""
Скрипт для автоматического применения миграций базы данных.
Может использоваться при запуске приложения в контейнере Docker.
"""
import os
import sys
import time
import subprocess
from urllib.parse import urlparse

import psycopg2

# Получение настроек из переменных окружения или значений по умолчанию
DB_URI = os.environ.get("DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/windi_messenger")
MAX_RETRIES = int(os.environ.get("DB_CONNECT_RETRIES", "5"))
RETRY_DELAY = int(os.environ.get("DB_CONNECT_RETRY_DELAY", "5"))

def parse_db_uri(uri):
    """Парсит Database URI и возвращает компоненты для подключения"""
    parsed = urlparse(uri)
    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'database': parsed.path[1:],
        'user': parsed.username,
        'password': parsed.password
    }

def check_database_connection(db_params):
    """Проверяет соединение с базой данных"""
    try:
        conn = psycopg2.connect(**db_params)
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return False

def wait_for_database(db_params):
    """Ожидает доступности базы данных"""
    retries = MAX_RETRIES
    while retries > 0:
        if check_database_connection(db_params):
            print("Подключение к базе данных установлено!")
            return True
        
        retries -= 1
        if retries > 0:
            print(f"Не удалось подключиться к базе данных. Повторная попытка через {RETRY_DELAY} секунд...")
            time.sleep(RETRY_DELAY)
    
    print("Не удалось подключиться к базе данных после нескольких попыток.")
    return False

def run_alembic_upgrade():
    """Запускает команду alembic upgrade head"""
    try:
        print("Применение миграций базы данных...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True
        )
        print("Миграции успешно применены:")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при применении миграций: {e}")
        print(f"Вывод: {e.stdout}")
        print(f"Ошибки: {e.stderr}")
        return False

def main():
    """Основная функция скрипта"""
    print("Запуск процесса миграции базы данных...")
    
    # Получение параметров подключения к базе данных
    db_params = parse_db_uri(DB_URI)
    print(f"Подключение к базе данных: {db_params['host']}:{db_params['port']}/{db_params['database']}")
    
    # Ожидание доступности базы данных
    if not wait_for_database(db_params):
        sys.exit(1)
    
    # Применение миграций
    if not run_alembic_upgrade():
        sys.exit(1)
    
    print("Процесс миграции базы данных успешно завершен!")

if __name__ == "__main__":
    main() 