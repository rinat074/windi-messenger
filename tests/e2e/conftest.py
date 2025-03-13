"""
Фикстуры для сквозных (end-to-end) тестов
"""
import os
import pytest
import logging
import httpx
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Константы для e2e тестов
API_URL = os.getenv("API_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CENTRIFUGO_URL = os.getenv("CENTRIFUGO_URL", "http://localhost:8001")
CENTRIFUGO_WS_URL = os.getenv("CENTRIFUGO_WS_URL", "ws://localhost:8001/connection/websocket")

logger = logging.getLogger("e2e_tests")

# ===== Фикстуры для e2e тестирования =====

class UserSession:
    """Класс для управления пользовательской сессией в e2e тестах"""
    
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.client = httpx.AsyncClient(base_url=API_URL, timeout=10.0)
        self.auth_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.centrifugo_token: Optional[str] = None
        self.chats: List[Dict[str, Any]] = []
    
    async def login(self) -> bool:
        """Авторизация пользователя"""
        try:
            response = await self.client.post(
                "/api/v1/users/login",
                json={
                    "email": self.email,
                    "password": self.password
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Ошибка авторизации: {response.status_code} {response.text}")
                return False
            
            data = response.json()
            self.auth_token = data.get("access_token")
            self.user_id = data.get("user", {}).get("id")
            
            # Обновляем заголовки для последующих запросов
            self.client.headers.update({"Authorization": f"Bearer {self.auth_token}"})
            
            # Получаем токен для Centrifugo
            await self.get_centrifugo_token()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка в процессе авторизации: {str(e)}")
            return False
    
    async def get_centrifugo_token(self) -> bool:
        """Получение токена для Centrifugo"""
        try:
            response = await self.client.post("/api/v1/centrifugo/token")
            
            if response.status_code != 200:
                logger.error(f"Ошибка получения токена Centrifugo: {response.status_code} {response.text}")
                return False
            
            data = response.json()
            self.centrifugo_token = data.get("token")
            return True
        except Exception as e:
            logger.error(f"Ошибка при получении токена Centrifugo: {str(e)}")
            return False
    
    async def load_chats(self) -> bool:
        """Загрузка списка чатов пользователя"""
        try:
            response = await self.client.get("/api/v1/chats")
            
            if response.status_code != 200:
                logger.error(f"Ошибка загрузки чатов: {response.status_code} {response.text}")
                return False
            
            data = response.json()
            self.chats = data.get("items", [])
            return True
        except Exception as e:
            logger.error(f"Ошибка при загрузке чатов: {str(e)}")
            return False
    
    async def create_chat(self, name: str, is_private: bool = False, user_ids: List[str] = None) -> Optional[str]:
        """Создание нового чата"""
        try:
            request_data = {
                "name": name,
                "is_private": is_private
            }
            
            if user_ids:
                request_data["user_ids"] = user_ids
            
            response = await self.client.post(
                "/api/v1/chats",
                json=request_data
            )
            
            if response.status_code not in (200, 201):
                logger.error(f"Ошибка создания чата: {response.status_code} {response.text}")
                return None
            
            data = response.json()
            chat_id = data.get("id")
            
            # Обновляем список чатов
            await self.load_chats()
            
            return chat_id
        except Exception as e:
            logger.error(f"Ошибка при создании чата: {str(e)}")
            return None
    
    async def send_message(self, chat_id: str, text: str) -> Optional[Dict[str, Any]]:
        """Отправка сообщения в чат"""
        import uuid
        
        try:
            client_message_id = f"e2e-test-{uuid.uuid4()}"
            
            response = await self.client.post(
                f"/api/v1/centrifugo/publish?chat_id={chat_id}",
                json={
                    "text": text,
                    "client_message_id": client_message_id
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Ошибка отправки сообщения: {response.status_code} {response.text}")
                return None
            
            data = response.json()
            return data
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {str(e)}")
            return None
    
    async def get_messages(self, chat_id: str, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """Получение сообщений чата"""
        try:
            response = await self.client.get(
                f"/api/v1/chats/{chat_id}/messages",
                params={"limit": limit}
            )
            
            if response.status_code != 200:
                logger.error(f"Ошибка получения сообщений: {response.status_code} {response.text}")
                return None
            
            data = response.json()
            return data.get("items", [])
        except Exception as e:
            logger.error(f"Ошибка при получении сообщений: {str(e)}")
            return None
    
    async def close(self):
        """Завершение сессии"""
        await self.client.aclose()


@pytest.fixture
async def user_session():
    """Создает сессию тестового пользователя"""
    # Данные тестового пользователя из окружения
    email = os.getenv("TEST_USER_EMAIL", "admin@example.com")
    password = os.getenv("TEST_USER_PASSWORD", "password123")
    
    session = UserSession(email, password)
    success = await session.login()
    
    if not success:
        pytest.skip("Не удалось создать пользовательскую сессию")
    
    try:
        yield session
    finally:
        await session.close()

@pytest.fixture
async def second_user_session():
    """Создает сессию второго тестового пользователя для тестирования взаимодействия"""
    # Данные второго тестового пользователя
    email = os.getenv("TEST_USER2_EMAIL", "user1@example.com")
    password = os.getenv("TEST_USER2_PASSWORD", "password123")
    
    session = UserSession(email, password)
    success = await session.login()
    
    if not success:
        pytest.skip("Не удалось создать вторую пользовательскую сессию")
    
    try:
        yield session
    finally:
        await session.close() 