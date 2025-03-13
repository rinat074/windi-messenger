"""
Фикстуры для модульных тестов
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Импортируем необходимые классы из приложения
try:
    from app.utils.centrifugo_manager import CentrifugoManager
    from app.core.centrifugo import CentrifugoClient
except ImportError:
    # Мокаем классы, если не удалось импортировать
    class CentrifugoManager:
        pass
        
    class CentrifugoClient:
        pass

# ===== Фикстуры для модульных тестов =====

@pytest.fixture
def mock_centrifugo_client_unit(monkeypatch):
    """Фикстура, предоставляющая мок для centrifugo_client (расширенная для unit-тестов)"""
    mock_client = AsyncMock()
    
    # Настройка основных методов
    mock_client.publish = AsyncMock(return_value={"success": True})
    mock_client.broadcast = AsyncMock(return_value={"success": True})
    mock_client.history = AsyncMock(return_value={"publications": []})
    mock_client.presence = AsyncMock(return_value={"clients": {}})
    
    # Методы для получения имен каналов
    mock_client.get_chat_channel_name = MagicMock(side_effect=lambda chat_id: f"chat:{chat_id}")
    mock_client.get_user_channel_name = MagicMock(side_effect=lambda user_id: f"user:{user_id}")
    mock_client.get_timestamp = MagicMock(return_value="2023-01-01T00:00:00Z")
    
    # Методы генерации токенов
    mock_client.generate_connection_token = MagicMock(return_value="test-connection-token")
    mock_client.generate_subscription_token = MagicMock(return_value="test-subscription-token")
    
    # Подменяем реальный клиент моком
    try:
        monkeypatch.setattr("app.utils.centrifugo_manager.centrifugo_client", mock_client)
        monkeypatch.setattr("app.core.centrifugo.centrifugo_client", mock_client)
    except Exception:
        pass
    
    return mock_client

@pytest.fixture
def test_centrifugo_manager():
    """Создает экземпляр CentrifugoManager для тестов"""
    return CentrifugoManager()

@pytest.fixture
def test_centrifugo_client():
    """Создает тестовый экземпляр CentrifugoClient"""
    return CentrifugoClient(
        centrifugo_url="http://localhost:8001",
        api_key="test_api_key",
        token_hmac_secret="test_secret",
        token_expire_seconds=3600
    )

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