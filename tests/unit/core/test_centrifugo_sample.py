"""
Пример модульных тестов для клиента Centrifugo
"""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

# Маркеры для модульных тестов
pytestmark = pytest.mark.unit

# Пример класса для тестирования
class DummyCentrifugoClient:
    """Простой класс для демонстрации тестирования"""
    
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.connected = False
    
    async def connect(self):
        """Подключение к Centrifugo"""
        # В реальном коде здесь был бы HTTP запрос
        self.connected = True
        return self.connected
    
    async def publish(self, channel, data):
        """Публикация сообщения в канал"""
        # В реальном коде здесь был бы HTTP запрос
        if not self.connected:
            raise RuntimeError("Client not connected")
        
        return {
            "success": True,
            "channel": channel,
            "data": data
        }
    
    def get_channel_name(self, prefix, id):
        """Получение имени канала"""
        return f"{prefix}:{id}"


# Пример тестов
def test_dummy_client_init():
    """Тест инициализации клиента"""
    # Подготовка данных
    base_url = "http://localhost:8000"
    api_key = "test-api-key"
    
    # Выполнение
    client = DummyCentrifugoClient(base_url, api_key)
    
    # Проверка
    assert client.base_url == base_url
    assert client.api_key == api_key
    assert client.connected == False


@pytest.mark.asyncio
async def test_dummy_client_connect():
    """Тест подключения к Centrifugo"""
    # Подготовка
    client = DummyCentrifugoClient("http://localhost:8000", "test-api-key")
    
    # Выполнение
    result = await client.connect()
    
    # Проверка
    assert result == True
    assert client.connected == True


@pytest.mark.asyncio
async def test_dummy_client_publish():
    """Тест публикации сообщения"""
    # Подготовка
    client = DummyCentrifugoClient("http://localhost:8000", "test-api-key")
    await client.connect()
    
    channel = "test:123"
    data = {"message": "Hello, world!", "timestamp": datetime.now().isoformat()}
    
    # Выполнение
    result = await client.publish(channel, data)
    
    # Проверка
    assert result["success"] == True
    assert result["channel"] == channel
    assert result["data"] == data


@pytest.mark.asyncio
async def test_dummy_client_publish_error():
    """Тест ошибки при публикации без подключения"""
    # Подготовка
    client = DummyCentrifugoClient("http://localhost:8000", "test-api-key")
    # Не подключаемся
    
    channel = "test:123"
    data = {"message": "Hello, world!"}
    
    # Проверка ошибки
    with pytest.raises(RuntimeError) as excinfo:
        await client.publish(channel, data)
    
    assert "Client not connected" in str(excinfo.value)


def test_get_channel_name():
    """Тест получения имени канала"""
    # Подготовка
    client = DummyCentrifugoClient("http://localhost:8000", "test-api-key")
    
    # Выполнение и проверка
    assert client.get_channel_name("chat", "123") == "chat:123"
    assert client.get_channel_name("user", "456") == "user:456"
    assert client.get_channel_name("presence", "789") == "presence:789"


@pytest.mark.asyncio
async def test_with_mock():
    """Тест с использованием мока"""
    # Подготовка
    with patch.object(DummyCentrifugoClient, 'publish', new_callable=AsyncMock) as mock_publish:
        mock_publish.return_value = {"success": True, "mocked": True}
        
        client = DummyCentrifugoClient("http://localhost:8000", "test-api-key")
        # Обходим проверку подключения для теста
        client.connected = True
        
        # Выполнение
        result = await client.publish("test:123", {"message": "Hello"})
        
        # Проверка
        assert result["success"] == True
        assert result["mocked"] == True
        mock_publish.assert_called_once_with("test:123", {"message": "Hello"}) 