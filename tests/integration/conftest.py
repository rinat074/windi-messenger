"""
Фикстуры для интеграционных тестов
"""
import os
import pytest
import logging
import uuid
import httpx
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Константы для интеграционных тестов
API_URL = os.getenv("API_URL", "http://localhost:8000")
CENTRIFUGO_URL = os.getenv("CENTRIFUGO_URL", "http://localhost:8001")
CENTRIFUGO_WS_URL = os.getenv("CENTRIFUGO_WS_URL", "ws://localhost:8001/connection/websocket")
API_KEY = os.getenv("CENTRIFUGO_API_KEY", "default-api-key")

logger = logging.getLogger("integration_tests")

# ===== Фикстуры для интеграционного тестирования =====

@pytest.fixture
async def test_message_data():
    """Создает тестовые данные для сообщения"""
    client_message_id = f"test-{uuid.uuid4()}"
    return {
        "text": f"Тестовое сообщение {datetime.now().isoformat()}",
        "client_message_id": client_message_id
    }

@pytest.fixture
async def create_test_message(auth_token, test_chat_id, test_message_data):
    """Создает тестовое сообщение в чате"""
    if not auth_token or not test_chat_id:
        pytest.skip("Отсутствуют необходимые данные")
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/api/v1/centrifugo/publish?chat_id={test_chat_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
                json=test_message_data,
                timeout=10.0
            )
            
            if response.status_code != 200:
                pytest.skip(f"Не удалось создать тестовое сообщение: {response.status_code} {response.text}")
                return None
            
            # Даем время на обработку сообщения
            await asyncio.sleep(1)
            
            return response.json()
    except Exception as e:
        pytest.skip(f"Ошибка при создании тестового сообщения: {str(e)}")
        return None

@pytest.fixture
async def get_message_history(auth_token, test_chat_id):
    """Получает историю сообщений чата"""
    if not auth_token or not test_chat_id:
        pytest.skip("Отсутствуют необходимые данные")
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_URL}/api/v1/chats/{test_chat_id}/messages",
                headers={"Authorization": f"Bearer {auth_token}"},
                params={"limit": 20},
                timeout=10.0
            )
            
            if response.status_code != 200:
                pytest.skip(f"Не удалось получить историю сообщений: {response.status_code} {response.text}")
                return None
            
            return response.json()
    except Exception as e:
        pytest.skip(f"Ошибка при получении истории сообщений: {str(e)}")
        return None

@pytest.fixture
async def check_centrifugo_presence(auth_token, test_chat_id):
    """Проверяет наличие пользователей в канале Centrifugo"""
    if not auth_token or not test_chat_id:
        pytest.skip("Отсутствуют необходимые данные")
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_URL}/api/v1/centrifugo/presence/{test_chat_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
                timeout=10.0
            )
            
            if response.status_code != 200:
                logger.warning(f"Не удалось получить данные о присутствии: {response.status_code} {response.text}")
                return None
            
            return response.json()
    except Exception as e:
        logger.warning(f"Ошибка при проверке присутствия: {str(e)}")
        return None 