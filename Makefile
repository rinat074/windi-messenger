# Makefile для проекта WinDI Messenger

.PHONY: help install install-dev test test-unit test-integration test-e2e test-performance report clean lint format docker-up docker-down run migrate migrate-up migrate-down create-migration db-seed find-unused clean-imports

# Переменные
PYTHON = python3
PIP = $(PYTHON) -m pip
PYTEST = pytest
PYTEST_FLAGS = -v
ALEMBIC = alembic
UVICORN = uvicorn
APP = app.main:app
PORT = 8000
HOST = 0.0.0.0
DOCKER_COMPOSE = docker-compose

# Помощь
help:
	@echo "Команды для WinDI Messenger:"
	@echo ""
	@echo "Установка и настройка:"
	@echo "  make install        - Установить основные зависимости"
	@echo "  make install-dev    - Установить зависимости для разработки"
	@echo "  make pre-commit     - Настроить pre-commit хуки"
	@echo ""
	@echo "Тестирование:"
	@echo "  make test           - Запустить все тесты"
	@echo "  make test-unit      - Запустить только модульные тесты"
	@echo "  make test-integration - Запустить только интеграционные тесты"
	@echo "  make test-e2e       - Запустить только E2E тесты"
	@echo "  make test-performance - Запустить тесты производительности"
	@echo "  make report         - Сгенерировать отчеты о тестировании"
	@echo ""
	@echo "Проверка кода:"
	@echo "  make lint           - Запустить все линтеры"
	@echo "  make format         - Отформатировать код"
	@echo "  make find-unused    - Найти неиспользуемые импорты"
	@echo "  make clean-imports  - Автоматически удалить неиспользуемые импорты"
	@echo ""
	@echo "База данных:"
	@echo "  make migrate        - Применить все миграции"
	@echo "  make migrate-up     - Выполнить миграцию вверх"
	@echo "  make migrate-down   - Выполнить миграцию вниз"
	@echo "  make create-migration name=migration_name - Создать новую миграцию"
	@echo "  make db-seed        - Заполнить базу тестовыми данными"
	@echo ""
	@echo "Запуск:"
	@echo "  make run            - Запустить сервер в режиме разработки"
	@echo "  make run-prod       - Запустить сервер в production режиме"
	@echo "  make docker-up      - Запустить все сервисы в Docker"
	@echo "  make docker-down    - Остановить все сервисы в Docker"
	@echo ""
	@echo "Очистка:"
	@echo "  make clean          - Очистить кэш Python и временные файлы"

# Установка
install:
	$(PIP) install -r requirements.txt

install-dev: install
	$(PIP) install -r requirements.dev.txt

pre-commit:
	$(PIP) install pre-commit
	pre-commit install

# Тестирование
test:
	$(PYTEST) $(PYTEST_FLAGS) tests/

test-unit:
	$(PYTEST) $(PYTEST_FLAGS) tests/unit/

test-integration:
	$(PYTEST) $(PYTEST_FLAGS) tests/integration/

test-e2e:
	$(PYTEST) $(PYTEST_FLAGS) tests/e2e/

test-performance:
	$(PYTEST) $(PYTEST_FLAGS) tests/performance/

report:
	$(PYTHON) scripts/generate_test_report.py --run-tests --test-type all

# Проверка кода
lint:
	flake8 app/ tests/ scripts/
	mypy app/ tests/ scripts/
	black --check app/ tests/ scripts/
	isort --check app/ tests/ scripts/

format:
	black app/ tests/ scripts/
	isort app/ tests/ scripts/

find-unused:
	$(PYTHON) scripts/find_unused_imports.py app/

clean-imports:
	$(PIP) install autoflake
	autoflake --remove-all-unused-imports --recursive --in-place app/
	autoflake --remove-all-unused-imports --recursive --in-place tests/
	autoflake --remove-all-unused-imports --recursive --in-place scripts/

# База данных
migrate:
	$(ALEMBIC) upgrade head

migrate-up:
	$(ALEMBIC) upgrade +1

migrate-down:
	$(ALEMBIC) downgrade -1

create-migration:
	$(ALEMBIC) revision --autogenerate -m "$(name)"

db-seed:
	$(PYTHON) scripts/create_test_data.py --yes

# Запуск
run:
	$(UVICORN) $(APP) --reload --host $(HOST) --port $(PORT)

run-prod:
	gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind $(HOST):$(PORT)

docker-up:
	$(DOCKER_COMPOSE) up -d

docker-down:
	$(DOCKER_COMPOSE) down

# Очистка
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .coverage -exec rm -rf {} +
	find . -type d -name htmlcov -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type f -name "coverage.xml" -delete
	find . -type f -name "*.log" -delete 