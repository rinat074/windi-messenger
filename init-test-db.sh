#!/bin/bash
set -e

# Переменные из environment
TEST_DB=${POSTGRES_TEST_DB:-windi_messenger_test}
USER=${POSTGRES_USER:-postgres}

# Создание тестовой базы данных
echo "Creating test database: $TEST_DB"
psql -v ON_ERROR_STOP=1 --username "$USER" <<-EOSQL
  CREATE DATABASE $TEST_DB;
  GRANT ALL PRIVILEGES ON DATABASE $TEST_DB TO $USER;
EOSQL

echo "Test database $TEST_DB created successfully" 