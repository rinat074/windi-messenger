# Руководство по тестированию WinDI Messenger

В данном документе описана система тестирования приложения WinDI Messenger, структура тестов, инструкции по запуску и рекомендации по написанию новых тестов.

## Структура тестов

Тесты разделены на несколько категорий в зависимости от их назначения и скорости выполнения:

### Модульные тесты (Unit Tests)

Расположены в директории `tests/unit/`. Предназначены для тестирования отдельных компонентов системы в изоляции.

- `tests/unit/core/` - тесты компонентов ядра приложения
  - `test_centrifugo.py` - тесты для клиента Centrifugo
  
- `tests/unit/utils/` - тесты утилит
  - `test_centrifugo_manager.py` - тесты для менеджера Centrifugo
  
- `tests/unit/models/` - тесты моделей данных
  - `test_base_models.py` - тесты базовых моделей данных

### Интеграционные тесты (Integration Tests)

Расположены в директории `tests/integration/`. Предназначены для проверки взаимодействия между компонентами.

- `tests/integration/api/` - тесты API endpoints
  - `test_chat_api.py` - тесты API для работы с чатами
  
- `tests/integration/centrifugo/` - тесты интеграции с Centrifugo
  - `test_centrifugo_client.py` - тесты интеграции с клиентом Centrifugo

### Сквозные тесты (End-to-End Tests)

Расположены в директории `tests/e2e/`. Проверяют полные пользовательские сценарии работы с системой.

- `tests/e2e/scenarios/` - тесты различных сценариев использования
  - `test_chat_scenario.py` - тест сценария создания чата и обмена сообщениями

### Тесты производительности (Performance Tests)

Расположены в директории `tests/performance/`. Тестируют производительность системы под нагрузкой.

- `tests/performance/load/` - нагрузочные тесты
  - `test_centrifugo_load.py` - нагрузочное тестирование Centrifugo

## Запуск тестов

### Через Python-скрипт

Для удобства запуска тестов был создан специальный скрипт `scripts/run_tests.py`. Он позволяет запускать различные типы тестов с нужными параметрами.

```bash
# Запуск всех модульных тестов
python scripts/run_tests.py unit

# Запуск интеграционных тестов с отчетом о покрытии
python scripts/run_tests.py integration -c

# Запуск e2e-тестов с подробным выводом
python scripts/run_tests.py e2e -v

# Запуск нагрузочных тестов в полном объеме
python scripts/run_tests.py performance -f

# Запуск всех тестов
python scripts/run_tests.py all
```

### Через shell-скрипт для e2e-тестов

Для запуска сквозных тестов с автоматической подготовкой окружения можно использовать скрипт `scripts/run_e2e_tests.sh`:

```bash
# Запуск e2e-тестов с автоматической подготовкой окружения
bash scripts/run_e2e_tests.sh
```

Этот скрипт автоматически запустит все необходимые сервисы (PostgreSQL, Redis, Centrifugo, API-сервер), применит миграции, создаст тестовые данные, запустит тесты и затем корректно остановит все сервисы.

### Через pytest напрямую

Также можно запускать тесты напрямую через pytest:

```bash
# Запуск модульных тестов
pytest tests/unit/

# Запуск интеграционных тестов
pytest tests/integration/

# Запуск e2e-тестов
pytest tests/e2e/

# Запуск тестов производительности
pytest tests/performance/

# Запуск тестов с определенным маркером
pytest -m unit
pytest -m integration
pytest -m e2e
pytest -m performance
pytest -m slow
```

## Генерация отчетов

Для генерации отчетов о тестировании можно использовать скрипт `scripts/generate_test_reports.py`:

```bash
# Генерация отчета о покрытии кода
python scripts/generate_test_reports.py coverage

# Генерация отчета о производительности
python scripts/generate_test_reports.py performance

# Генерация всех типов отчетов
python scripts/generate_test_reports.py all
```

Отчеты сохраняются в директории `test_reports/`.

## Фикстуры

В проекте используются различные фикстуры для подготовки тестового окружения:

### Общие фикстуры (`conftest.py`)

- `auth_token` - получение токена авторизации
- `auth_headers` - получение заголовков авторизации
- `centrifugo_token` - получение токена для Centrifugo
- `test_chat_id` - создание или получение тестового чата
- `mock_centrifugo_client` - мок для клиента Centrifugo

### Фикстуры для модульных тестов (`unit/conftest.py`)

- `mock_centrifugo_client_unit` - расширенный мок для клиента Centrifugo
- `test_centrifugo_manager` - экземпляр CentrifugoManager для тестов
- `test_centrifugo_client` - экземпляр CentrifugoClient для тестов
- `mock_httpx_client` - мок для HTTP-клиента

### Фикстуры для интеграционных тестов (`integration/conftest.py`)

- `test_message_data` - данные для тестового сообщения
- `create_test_message` - создание тестового сообщения
- `get_message_history` - получение истории сообщений
- `check_centrifugo_presence` - проверка присутствия пользователей

### Фикстуры для e2e тестов (`e2e/conftest.py`)

- `user_session` - сессия основного пользователя
- `second_user_session` - сессия второго пользователя

### Фикстуры для тестов производительности (`performance/conftest.py`)

- `load_test_results` - объект для сбора результатов тестов
- `authenticated_session` - аутентифицированная сессия
- `test_chat_for_load` - тестовый чат для нагрузочных тестов

## Рекомендации по написанию новых тестов

### Общие рекомендации

1. Размещайте тесты в соответствующих директориях в зависимости от их типа.
2. Используйте маркеры для категоризации тестов.
3. Не создавайте зависимости между тестами.
4. Используйте фикстуры для подготовки тестового окружения.
5. Удаляйте созданные тестовые данные после выполнения тестов.

### Модульные тесты

```python
import pytest

@pytest.mark.unit
def test_some_function():
    # Подготовка
    input_data = ...
    
    # Выполнение
    result = some_function(input_data)
    
    # Проверка
    assert result == expected_result
```

### Интеграционные тесты

```python
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_endpoint(auth_headers):
    # Подготовка
    data = {...}
    
    # Выполнение запроса
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_URL}/api/v1/resource", 
                                    headers=auth_headers, 
                                    json=data)
    
    # Проверка
    assert response.status_code == 201
    assert "id" in response.json()
```

### Сквозные тесты

```python
import pytest

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_user_scenario(user_session):
    # Выполнение сценария
    result = await user_session.perform_action()
    
    # Проверка
    assert result is not None
    assert result.status == "success"
```

### Тесты производительности

```python
import pytest

@pytest.mark.performance
@pytest.mark.asyncio
@pytest.mark.parametrize("concurrency", [1, 5, 10])
async def test_endpoint_performance(concurrency, load_test_results):
    # Выполнение теста производительности
    # ...
    
    # Проверка результатов
    assert results.success_rate > 95
    assert results.avg_response_time < 0.5
```

## Работа с моками

Для модульных тестов часто требуется использовать моки внешних зависимостей:

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.mark.unit
@patch("app.module.external_dependency")
def test_function_with_mocked_dependency(mock_dependency):
    # Настройка мока
    mock_dependency.method.return_value = expected_result
    
    # Выполнение тестируемого кода
    result = function_under_test()
    
    # Проверка результата
    assert result == expected_result
    
    # Проверка вызова мока
    mock_dependency.method.assert_called_once_with(expected_args)
```

## Тестирование асинхронного кода

Для тестирования асинхронного кода используется `pytest-asyncio`:

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    # Выполнение асинхронного кода
    result = await async_function()
    
    # Проверка результата
    assert result == expected_result
```

## Дополнительные ресурсы

- [Документация pytest](https://docs.pytest.org/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [pytest-cov](https://github.com/pytest-dev/pytest-cov)
- [Unittest.mock](https://docs.python.org/3/library/unittest.mock.html) 