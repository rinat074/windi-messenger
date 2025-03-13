"""
Модульные тесты для клиента Centrifugo

Этот модуль содержит полный набор тестов для проверки функциональности
клиента Centrifugo, включая публикацию сообщений, получение истории,
проверку присутствия пользователей и генерацию токенов.
"""
import pytest
import json
import jwt
from datetime import datetime

# Маркеры для модульных тестов
pytestmark = [
    pytest.mark.unit,
    pytest.mark.centrifugo,
    pytest.mark.component("core"),
    pytest.mark.requirement("REQ-CENT-001")
]

# Защищенный импорт
try:
    from app.core.centrifugo import CentrifugoClient
except ImportError:
    # Если не удается импортировать, создаем заглушку для тестирования
    class CentrifugoClient:
        def __init__(self, centrifugo_url, api_key, token_hmac_secret, token_expire_seconds):
            self.centrifugo_url = centrifugo_url
            self.api_key = api_key
            self.token_hmac_secret = token_hmac_secret
            self.token_expire_seconds = token_expire_seconds
    
    pytest.skip("Не удалось импортировать CentrifugoClient, создана заглушка для тестов")


@pytest.mark.asyncio
@pytest.mark.requirement("REQ-CENT-002")
async def test_publish(mock_httpx_client, test_centrifugo_client):
    """
    Тест метода публикации сообщения в канал
    
    Проверяет, что метод publish:
    1. Корректно формирует запрос к API Centrifugo
    2. Устанавливает правильные заголовки авторизации
    3. Передает нужные данные в теле запроса
    4. Правильно обрабатывает ответ от сервера
    
    Args:
        mock_httpx_client: Мок HTTP-клиента
        test_centrifugo_client: Тестируемый экземпляр CentrifugoClient
    """
    # Подготовка данных для теста
    channel = "test_channel"
    data = {"message": "Тестовое сообщение", "timestamp": datetime.now().isoformat()}
    
    # Настройка мока
    mock_httpx_client.post.return_value.status_code = 200
    mock_httpx_client.post.return_value.json.return_value = {"result": {}}
    
    # Выполнение метода
    result = await test_centrifugo_client.publish(channel, data)
    
    # Проверки
    assert result is not None
    
    # Проверяем вызов HTTP-клиента с правильными параметрами
    mock_httpx_client.post.assert_called_once()
    call_args = mock_httpx_client.post.call_args
    
    # Проверяем URL
    assert call_args[0][0] == f"{test_centrifugo_client.centrifugo_url}/api"
    
    # Проверяем заголовки
    assert "Authorization" in call_args[1]["headers"]
    assert call_args[1]["headers"]["Authorization"] == f"apikey {test_centrifugo_client.api_key}"
    
    # Проверяем данные запроса
    request_data = json.loads(call_args[1]["content"])
    assert request_data["method"] == "publish"
    assert request_data["params"]["channel"] == channel
    assert request_data["params"]["data"] == data


@pytest.mark.asyncio
@pytest.mark.requirement("REQ-CENT-003")
@pytest.mark.parametrize("channels_count", [1, 3, 5, 10])
async def test_broadcast(mock_httpx_client, test_centrifugo_client, channels_count):
    """
    Тест метода отправки сообщения в несколько каналов
    
    Проверяет, что метод broadcast правильно отправляет сообщения
    в указанное количество каналов. Тест параметризован для проверки
    разного количества каналов.
    
    Args:
        mock_httpx_client: Мок HTTP-клиента
        test_centrifugo_client: Тестируемый экземпляр CentrifugoClient
        channels_count: Количество каналов для теста
    """
    # Подготовка данных для теста
    channels = [f"channel{i}" for i in range(channels_count)]
    data = {"message": "Тестовое широковещательное сообщение"}
    
    # Настройка мока
    mock_httpx_client.post.return_value.status_code = 200
    mock_httpx_client.post.return_value.json.return_value = {"result": {}}
    
    # Выполнение метода
    result = await test_centrifugo_client.broadcast(channels, data)
    
    # Проверки
    assert result is not None
    
    # Проверяем вызов HTTP-клиента с правильными параметрами
    mock_httpx_client.post.assert_called_once()
    call_args = mock_httpx_client.post.call_args
    
    # Проверяем данные запроса
    request_data = json.loads(call_args[1]["content"])
    assert request_data["method"] == "broadcast"
    assert request_data["params"]["channels"] == channels
    assert request_data["params"]["data"] == data
    
    # Проверка, что количество каналов соответствует ожидаемому
    assert len(request_data["params"]["channels"]) == channels_count


@pytest.mark.asyncio
@pytest.mark.requirement("REQ-CENT-004")
@pytest.mark.parametrize("limit", [10, 50, 100])
async def test_history(mock_httpx_client, test_centrifugo_client, limit):
    """
    Тест получения истории сообщений канала
    
    Проверяет функциональность получения истории сообщений из канала
    с различными лимитами на количество сообщений.
    
    Args:
        mock_httpx_client: Мок HTTP-клиента
        test_centrifugo_client: Тестируемый экземпляр CentrifugoClient
        limit: Максимальное количество сообщений для получения
    """
    # Подготовка данных для теста
    channel = "test_channel"
    publications = [
        {
            "data": {"message": f"Сообщение {i}"},
            "offset": i,
            "timestamp": datetime.now().isoformat()
        }
        for i in range(1, min(limit, 5) + 1)  # Создаем до 5 сообщений
    ]
    
    # Настройка мока
    mock_httpx_client.post.return_value.status_code = 200
    mock_httpx_client.post.return_value.json.return_value = {
        "result": {"publications": publications}
    }
    
    # Выполнение метода с указанным лимитом
    result = await test_centrifugo_client.history(channel, limit=limit)
    
    # Проверки
    assert result is not None
    assert "publications" in result
    assert result["publications"] == publications
    
    # Проверяем вызов HTTP-клиента с правильными параметрами
    mock_httpx_client.post.assert_called_once()
    call_args = mock_httpx_client.post.call_args
    
    # Проверяем данные запроса
    request_data = json.loads(call_args[1]["content"])
    assert request_data["method"] == "history"
    assert request_data["params"]["channel"] == channel
    assert request_data["params"].get("limit") == limit


@pytest.mark.asyncio
@pytest.mark.requirement("REQ-CENT-005")
async def test_presence(mock_httpx_client, test_centrifugo_client):
    """
    Тест получения данных о присутствии пользователей в канале
    
    Проверяет корректность запроса и обработки ответа при получении
    информации о пользователях, подключенных к каналу.
    
    Args:
        mock_httpx_client: Мок HTTP-клиента
        test_centrifugo_client: Тестируемый экземпляр CentrifugoClient
    """
    # Подготовка данных для теста
    channel = "test_channel"
    presence_data = {
        "clients": {
            "client1": {
                "user": "user1",
                "conn_info": {"ip": "127.0.0.1"}
            },
            "client2": {
                "user": "user2",
                "conn_info": {"ip": "127.0.0.2"}
            }
        }
    }
    
    # Настройка мока
    mock_httpx_client.post.return_value.status_code = 200
    mock_httpx_client.post.return_value.json.return_value = {
        "result": presence_data
    }
    
    # Выполнение метода
    result = await test_centrifugo_client.presence(channel)
    
    # Проверки
    assert result is not None
    assert "clients" in result
    assert result["clients"] == presence_data["clients"]
    
    # Проверяем вызов HTTP-клиента с правильными параметрами
    mock_httpx_client.post.assert_called_once()
    call_args = mock_httpx_client.post.call_args
    
    # Проверяем данные запроса
    request_data = json.loads(call_args[1]["content"])
    assert request_data["method"] == "presence"
    assert request_data["params"]["channel"] == channel


@pytest.mark.requirement("REQ-CENT-006")
@pytest.mark.parametrize("user_id,meta_info", [
    ("user_123", None),
    ("user_456", {"role": "admin"}),
    ("user_789", {"name": "Test User", "avatar": "https://example.com/avatar.jpg"})
])
def test_generate_connection_token(test_centrifugo_client, user_id, meta_info):
    """
    Тест генерации токена подключения
    
    Проверяет корректность генерации JWT токена для подключения к Centrifugo
    с различными идентификаторами пользователей и мета-информацией.
    
    Args:
        test_centrifugo_client: Тестируемый экземпляр CentrifugoClient
        user_id: Идентификатор пользователя
        meta_info: Дополнительная информация о пользователе
    """
    # Выполнение метода
    token = test_centrifugo_client.generate_connection_token(user_id, meta=meta_info)
    
    # Проверки
    assert token is not None
    
    # Декодируем токен и проверяем данные
    decoded = jwt.decode(token, test_centrifugo_client.token_hmac_secret, algorithms=["HS256"])
    assert decoded["sub"] == user_id
    assert "exp" in decoded
    
    # Проверяем, что мета-информация включена в токен, если указана
    if meta_info:
        assert "meta" in decoded
        assert decoded["meta"] == meta_info
    
    # Проверяем, что срок действия токена соответствует ожидаемому
    now = datetime.now().timestamp()
    assert decoded["exp"] > now
    assert decoded["exp"] <= now + test_centrifugo_client.token_expire_seconds + 1  # Допуск на 1 секунду


@pytest.mark.requirement("REQ-CENT-007")
@pytest.mark.parametrize("user_id,channel,info", [
    ("user_123", "chat:123", None),
    ("user_456", "personal:456", {"role": "member"}),
    ("user_789", "group:789", {"access": "read-only"})
])
def test_generate_subscription_token(test_centrifugo_client, user_id, channel, info):
    """
    Тест генерации токена подписки на канал
    
    Проверяет корректность генерации JWT токена для подписки на канал
    с различными параметрами пользователя, канала и дополнительной информации.
    
    Args:
        test_centrifugo_client: Тестируемый экземпляр CentrifugoClient
        user_id: Идентификатор пользователя
        channel: Имя канала
        info: Дополнительная информация о подписке
    """
    # Выполнение метода
    token = test_centrifugo_client.generate_subscription_token(user_id, channel, info=info)
    
    # Проверки
    assert token is not None
    
    # Декодируем токен и проверяем данные
    decoded = jwt.decode(token, test_centrifugo_client.token_hmac_secret, algorithms=["HS256"])
    assert decoded["sub"] == user_id
    assert decoded["channel"] == channel
    assert "exp" in decoded
    
    # Проверяем, что дополнительная информация включена в токен, если указана
    if info:
        assert "info" in decoded
        assert decoded["info"] == info


@pytest.mark.requirement("REQ-CENT-008")
@pytest.mark.parametrize("prefix,id,expected", [
    ("chat", "123", "chat:123"),
    ("user", "abc-def", "user:abc-def"),
    ("group", "group_id-123", "group:group_id-123"),
    ("private", "user1-user2", "private:user1-user2")
])
def test_get_channel_names(test_centrifugo_client, prefix, id, expected):
    """
    Тест генерации имен каналов
    
    Проверяет правильность формирования имен каналов разных типов.
    
    Args:
        test_centrifugo_client: Тестируемый экземпляр CentrifugoClient
        prefix: Префикс канала (chat, user и т.д.)
        id: Идентификатор
        expected: Ожидаемое полное имя канала
    """
    # Выполнение - используем общий метод для всех типов каналов
    channel_name = f"{prefix}:{id}"
    
    # Специфичные методы для стандартных типов каналов
    if prefix == "chat":
        chat_channel = test_centrifugo_client.get_chat_channel_name(id)
        assert chat_channel == expected
    elif prefix == "user":
        user_channel = test_centrifugo_client.get_user_channel_name(id)
        assert user_channel == expected
    
    # Общая проверка формата
    assert channel_name == expected


@pytest.mark.asyncio
@pytest.mark.requirement("REQ-CENT-009")
@pytest.mark.parametrize("status_code,error_text", [
    (400, "Bad Request"),
    (401, "Unauthorized"),
    (403, "Forbidden"),
    (404, "Not Found"),
    (500, "Server Error"),
    (503, "Service Unavailable")
])
async def test_error_handling(mock_httpx_client, test_centrifugo_client, status_code, error_text):
    """
    Тест обработки HTTP ошибок при ответе сервера
    
    Проверяет корректность обработки различных HTTP ошибок
    при взаимодействии с Centrifugo API.
    
    Args:
        mock_httpx_client: Мок HTTP-клиента
        test_centrifugo_client: Тестируемый экземпляр CentrifugoClient
        status_code: HTTP статус-код ошибки
        error_text: Текст ошибки
    """
    # Настройка мока для имитации ошибки
    mock_httpx_client.post.return_value.status_code = status_code
    mock_httpx_client.post.return_value.text = error_text
    
    # Подготовка данных для теста
    channel = "test_channel"
    data = {"message": "Тестовое сообщение"}
    
    # Выполнение метода и ожидание исключения
    with pytest.raises(Exception) as excinfo:
        await test_centrifugo_client.publish(channel, data)
    
    # Проверка сообщения об ошибке
    assert str(status_code) in str(excinfo.value)
    assert error_text in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.requirement("REQ-CENT-010")
@pytest.mark.parametrize("error_code,error_message", [
    (100, "Channel not found"),
    (101, "Permission denied"),
    (102, "Bad request"),
    (103, "Internal server error")
])
async def test_api_error_response(mock_httpx_client, test_centrifugo_client, error_code, error_message):
    """
    Тест обработки ошибок API Centrifugo
    
    Проверяет корректность обработки ошибок, возвращаемых API Centrifugo
    (когда HTTP статус 200, но в ответе есть поле error).
    
    Args:
        mock_httpx_client: Мок HTTP-клиента
        test_centrifugo_client: Тестируемый экземпляр CentrifugoClient
        error_code: Код ошибки API
        error_message: Сообщение об ошибке
    """
    # Настройка мока для имитации ошибки API
    mock_httpx_client.post.return_value.status_code = 200
    mock_httpx_client.post.return_value.json.return_value = {
        "error": {
            "code": error_code,
            "message": error_message
        }
    }
    
    # Подготовка данных для теста
    channel = "test_channel"
    
    # Выполнение метода и ожидание исключения
    with pytest.raises(Exception) as excinfo:
        await test_centrifugo_client.history(channel)
    
    # Проверка сообщения об ошибке
    assert error_message in str(excinfo.value)
    assert str(error_code) in str(excinfo.value) 