"""
Модульные тесты для клиента Centrifugo
"""
import pytest
import json
import jwt
from unittest.mock import patch, AsyncMock

from app.core.centrifugo import CentrifugoClient


@pytest.fixture
def mock_httpx_client():
    """Фикстура для мокирования HTTP-клиента"""
    with patch("httpx.AsyncClient") as mock_client:
        # Настраиваем успешный ответ по умолчанию
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock()
        mock_instance.post.return_value = AsyncMock()
        mock_instance.post.return_value.status_code = 200
        mock_instance.post.return_value.json = AsyncMock(return_value={"result": {}})
        
        # Возвращаем инстанс как результат вызова httpx.AsyncClient()
        mock_client.return_value = mock_instance
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        
        yield mock_instance


@pytest.fixture
def centrifugo_client():
    """Создает тестовый экземпляр клиента Centrifugo"""
    client = CentrifugoClient(
        centrifugo_url="http://localhost:8001",
        api_key="test_api_key",
        token_hmac_secret="test_secret",
        token_expire_seconds=3600
    )
    return client


@pytest.mark.asyncio
async def test_publish(centrifugo_client, mock_httpx_client):
    """Тест публикации сообщения в канал"""
    # Настройка тестовых данных
    channel = "test:channel"
    data = {"message": "test_message", "timestamp": "2023-01-01T00:00:00Z"}
    
    # Вызов тестируемого метода
    await centrifugo_client.publish(channel, data)
    
    # Проверка вызова HTTP-клиента с правильными параметрами
    mock_httpx_client.post.assert_called_once()
    args, kwargs = mock_httpx_client.post.call_args
    
    assert args[0] == "http://localhost:8001/api"
    assert kwargs["headers"]["Authorization"] == "apikey test_api_key"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    
    # Проверка JSON-данных запроса
    request_data = json.loads(kwargs["content"])
    assert request_data["method"] == "publish"
    assert request_data["params"]["channel"] == channel
    assert request_data["params"]["data"] == data


@pytest.mark.asyncio
async def test_broadcast(centrifugo_client, mock_httpx_client):
    """Тест публикации сообщения в несколько каналов"""
    # Настройка тестовых данных
    channels = ["test:channel1", "test:channel2"]
    data = {"message": "test_message", "timestamp": "2023-01-01T00:00:00Z"}
    
    # Вызов тестируемого метода
    await centrifugo_client.broadcast(channels, data)
    
    # Проверка вызова HTTP-клиента с правильными параметрами
    mock_httpx_client.post.assert_called_once()
    args, kwargs = mock_httpx_client.post.call_args
    
    assert args[0] == "http://localhost:8001/api"
    
    # Проверка JSON-данных запроса
    request_data = json.loads(kwargs["content"])
    assert request_data["method"] == "broadcast"
    assert request_data["params"]["channels"] == channels
    assert request_data["params"]["data"] == data


@pytest.mark.asyncio
async def test_history(centrifugo_client, mock_httpx_client):
    """Тест получения истории сообщений канала"""
    # Настройка тестовых данных
    channel = "test:channel"
    
    # Настраиваем мок для возврата истории
    history_data = {
        "publications": [
            {"data": {"message": "test1"}},
            {"data": {"message": "test2"}}
        ]
    }
    mock_httpx_client.post.return_value.json.return_value = {"result": history_data}
    
    # Вызов тестируемого метода
    result = await centrifugo_client.history(channel)
    
    # Проверка вызова HTTP-клиента с правильными параметрами
    mock_httpx_client.post.assert_called_once()
    args, kwargs = mock_httpx_client.post.call_args
    
    # Проверка JSON-данных запроса
    request_data = json.loads(kwargs["content"])
    assert request_data["method"] == "history"
    assert request_data["params"]["channel"] == channel
    
    # Проверка результата
    assert result == history_data
    assert len(result["publications"]) == 2
    assert result["publications"][0]["data"]["message"] == "test1"


@pytest.mark.asyncio
async def test_presence(centrifugo_client, mock_httpx_client):
    """Тест получения информации о пользователях в канале"""
    # Настройка тестовых данных
    channel = "test:channel"
    
    # Настраиваем мок для возврата информации о presence
    presence_data = {
        "clients": {
            "client1": {"user": "user1", "connected_at": 1609459200},
            "client2": {"user": "user2", "connected_at": 1609459300}
        }
    }
    mock_httpx_client.post.return_value.json.return_value = {"result": presence_data}
    
    # Вызов тестируемого метода
    result = await centrifugo_client.presence(channel)
    
    # Проверка вызова HTTP-клиента с правильными параметрами
    mock_httpx_client.post.assert_called_once()
    args, kwargs = mock_httpx_client.post.call_args
    
    # Проверка JSON-данных запроса
    request_data = json.loads(kwargs["content"])
    assert request_data["method"] == "presence"
    assert request_data["params"]["channel"] == channel
    
    # Проверка результата
    assert result == presence_data
    assert len(result["clients"]) == 2
    assert "client1" in result["clients"]
    assert result["clients"]["client1"]["user"] == "user1"


def test_generate_connection_token(centrifugo_client):
    """Тест генерации токена для подключения к Centrifugo"""
    # Настройка тестовых данных
    user_id = "test_user"
    info = {"name": "Test User"}
    
    # Вызов тестируемого метода
    token = centrifugo_client.generate_connection_token(user_id, info)
    
    # Декодирование токена и проверка содержимого
    decoded = jwt.decode(
        token,
        "test_secret",
        algorithms=["HS256"],
        options={"verify_signature": True}
    )
    
    # Проверка полей токена
    assert decoded["sub"] == user_id
    assert decoded["info"] == info
    assert "exp" in decoded
    assert "iat" in decoded


def test_generate_subscription_token(centrifugo_client):
    """Тест генерации токена для подписки на каналы"""
    # Настройка тестовых данных
    user_id = "test_user"
    channel = "test:channel"
    
    # Вызов тестируемого метода
    token = centrifugo_client.generate_subscription_token(user_id, channel)
    
    # Декодирование токена и проверка содержимого
    decoded = jwt.decode(
        token,
        "test_secret",
        algorithms=["HS256"],
        options={"verify_signature": True}
    )
    
    # Проверка полей токена
    assert decoded["sub"] == user_id
    assert decoded["channel"] == channel
    assert "exp" in decoded


def test_get_channel_names(centrifugo_client):
    """Тест получения названий каналов"""
    # Тест названия канала чата
    chat_id = "123"
    chat_channel = centrifugo_client.get_chat_channel_name(chat_id)
    assert chat_channel == "chat:123"
    
    # Тест названия личного канала пользователя
    user_id = "456"
    user_channel = centrifugo_client.get_user_channel_name(user_id)
    assert user_channel == "user:456"


@pytest.mark.asyncio
async def test_error_handling(centrifugo_client, mock_httpx_client):
    """Тест обработки ошибок при взаимодействии с Centrifugo API"""
    # Настраиваем мок на возврат ошибки
    mock_httpx_client.post.return_value.status_code = 500
    mock_httpx_client.post.return_value.text = "Internal Server Error"
    
    # Вызов тестируемого метода с ожиданием исключения
    with pytest.raises(Exception) as excinfo:
        await centrifugo_client.publish("test:channel", {"message": "test"})
    
    # Проверка сообщения об ошибке
    assert "Error publishing to Centrifugo" in str(excinfo.value)
    assert "500" in str(excinfo.value)


@pytest.mark.asyncio
async def test_api_error_response(centrifugo_client, mock_httpx_client):
    """Тест обработки ошибок в ответе Centrifugo API"""
    # Настраиваем мок на возврат успешного статуса, но с ошибкой в ответе
    mock_httpx_client.post.return_value.status_code = 200
    mock_httpx_client.post.return_value.json.return_value = {
        "error": {
            "code": 100,
            "message": "Invalid channel"
        }
    }
    
    # Вызов тестируемого метода с ожиданием исключения
    with pytest.raises(Exception) as excinfo:
        await centrifugo_client.publish("test:channel", {"message": "test"})
    
    # Проверка сообщения об ошибке
    assert "Centrifugo API error" in str(excinfo.value)
    assert "Invalid channel" in str(excinfo.value) 