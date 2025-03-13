"""
Фикстуры и вспомогательные классы для тестов производительности
"""
import os
import time
import json
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import aiohttp
import pytest
from dotenv import load_dotenv
import httpx

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("performance_tests")

# Константы для тестов производительности
API_URL = os.getenv("API_URL", "http://localhost:8000")
CENTRIFUGO_URL = os.getenv("CENTRIFUGO_URL", "http://localhost:8001")
CENTRIFUGO_WS_URL = os.getenv("CENTRIFUGO_WS_URL", "ws://localhost:8001/connection/websocket")
AUTH_EMAIL = os.getenv("TEST_USER_EMAIL", "admin@example.com")
AUTH_PASSWORD = os.getenv("TEST_USER_PASSWORD", "password123")

# Используем полную версию нагрузочных тестов, если задана переменная окружения
FULL_LOAD_TEST = os.getenv("FULL_LOAD_TEST", "0") == "1"

# Конфигурация для нагрузочных тестов
DEFAULT_REQUESTS = 20 if not FULL_LOAD_TEST else 1000
DEFAULT_CONCURRENCY = 2 if not FULL_LOAD_TEST else 50

# ===== Фикстуры для нагрузочных тестов =====

@pytest.fixture
def performance_config():
    """Конфигурация для нагрузочных тестов"""
    return {
        "requests": DEFAULT_REQUESTS,
        "concurrency": DEFAULT_CONCURRENCY,
        "api_url": API_URL,
        "centrifugo_url": CENTRIFUGO_URL,
        "centrifugo_ws_url": CENTRIFUGO_WS_URL,
        "api_key": os.getenv("CENTRIFUGO_API_KEY", "default-api-key"),
        "token_secret": os.getenv("CENTRIFUGO_TOKEN_HMAC_SECRET", "secret-key-for-tests"),
        "full_load": FULL_LOAD_TEST
    }

@pytest.fixture
def performance_result_handler():
    """Обработчик результатов нагрузочных тестов"""
    class ResultHandler:
        def __init__(self):
            self.results = {
                "start_time": datetime.now().isoformat(),
                "requests": 0,
                "successful": 0,
                "failed": 0,
                "total_time": 0,
                "avg_time": 0,
                "min_time": float('inf'),
                "max_time": 0,
                "times": [],
                "percentiles": {}
            }
        
        def add_result(self, success, duration):
            """Добавление результата запроса"""
            self.results["requests"] += 1
            
            if success:
                self.results["successful"] += 1
            else:
                self.results["failed"] += 1
            
            self.results["total_time"] += duration
            self.results["times"].append(duration)
            
            if duration < self.results["min_time"]:
                self.results["min_time"] = duration
            
            if duration > self.results["max_time"]:
                self.results["max_time"] = duration
        
        def finalize(self):
            """Вычисление финальных статистик"""
            self.results["end_time"] = datetime.now().isoformat()
            
            if self.results["requests"] > 0:
                self.results["avg_time"] = self.results["total_time"] / self.results["requests"]
                
                # Сортируем времена для вычисления процентилей
                sorted_times = sorted(self.results["times"])
                
                # Вычисляем основные процентили
                percentiles = {50: 0, 90: 0, 95: 0, 99: 0}
                for p in percentiles.keys():
                    idx = int(len(sorted_times) * p / 100)
                    if idx < len(sorted_times):
                        percentiles[p] = sorted_times[idx]
                
                self.results["percentiles"] = percentiles
            
            # Освобождаем память, удаляя массив всех времен
            if "times" in self.results:
                del self.results["times"]
            
            return self.results
        
        def save_to_file(self, filename):
            """Сохранение результатов в файл"""
            try:
                with open(filename, 'w') as f:
                    json.dump(self.results, f, indent=2)
                logger.info(f"Результаты сохранены в файл: {filename}")
                return True
            except Exception as e:
                logger.error(f"Ошибка при сохранении результатов: {e}")
                return False
    
    return ResultHandler()

@pytest.fixture
async def test_user_credentials():
    """Получение учетных данных тестового пользователя"""
    # Берем данные из переменных окружения
    email = os.getenv("TEST_USER_EMAIL", "admin@example.com")
    password = os.getenv("TEST_USER_PASSWORD", "password123")
    
    return {
        "email": email,
        "password": password
    }

@pytest.fixture
async def test_auth_token(test_user_credentials):
    """Получение токена авторизации"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/api/v1/users/login",
                json={
                    "email": test_user_credentials["email"],
                    "password": test_user_credentials["password"]
                },
                timeout=10.0
            )
            
            if response.status_code != 200:
                logger.error(f"Не удалось авторизоваться: {response.status_code} {response.text}")
                return None
            
            data = response.json()
            return data.get("access_token")
    except Exception as e:
        logger.error(f"Ошибка при получении токена: {str(e)}")
        return None

@pytest.fixture
async def test_performance_chat(test_auth_token):
    """Создание тестового чата для нагрузочных тестов"""
    if not test_auth_token:
        logger.error("Отсутствует токен авторизации")
        return None
    
    # Префикс для имени чата
    chat_name = f"Performance Test Chat {uuid.uuid4()}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/api/v1/chats",
                headers={"Authorization": f"Bearer {test_auth_token}"},
                json={
                    "name": chat_name,
                    "is_private": False
                },
                timeout=10.0
            )
            
            if response.status_code != 201 and response.status_code != 200:
                logger.error(f"Не удалось создать тестовый чат: {response.status_code} {response.text}")
                return None
            
            data = response.json()
            chat_id = data.get("id")
            
            if not chat_id:
                logger.error("ID чата не найден в ответе сервера")
                return None
            
            logger.info(f"Создан чат для нагрузочных тестов: {chat_id}")
            return chat_id
    except Exception as e:
        logger.error(f"Ошибка при создании тестового чата: {str(e)}")
        return None

class LoadTestResults:
    """Класс для сбора и анализа результатов нагрузочного тестирования"""
    
    def __init__(self):
        self.request_times: List[float] = []  # Список времен выполнения запросов
        self.error_count: int = 0     # Счетчик ошибок
        self.success_count: int = 0   # Счетчик успешных запросов
        self.start_time: Optional[float] = None   # Время начала теста
        self.end_time: Optional[float] = None     # Время окончания теста
        self.request_details: List[Dict[str, Any]] = []  # Детали каждого запроса
    
    def start(self) -> None:
        """Начало тестирования"""
        self.start_time = time.time()
    
    def end(self) -> None:
        """Окончание тестирования"""
        self.end_time = time.time()
    
    def add_request(self, duration: float, success: bool, details: Dict[str, Any] = None) -> None:
        """Добавление результата запроса"""
        self.request_times.append(duration)
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        self.request_details.append({
            "duration": duration,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Получение сводки результатов тестирования"""
        if not self.request_times:
            return {"error": "No requests recorded"}
        
        total_duration = self.end_time - self.start_time if self.end_time else 0
        
        summary = {
            "total_requests": self.success_count + self.error_count,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "success_rate": round(self.success_count / (self.success_count + self.error_count) * 100, 2) if (self.success_count + self.error_count) > 0 else 0,
            "total_duration": round(total_duration, 2),
            "requests_per_second": round((self.success_count + self.error_count) / total_duration, 2) if total_duration > 0 else 0,
            "min_request_time": round(min(self.request_times), 3) if self.request_times else 0,
            "max_request_time": round(max(self.request_times), 3) if self.request_times else 0,
            "avg_request_time": round(sum(self.request_times) / len(self.request_times), 3) if self.request_times else 0
        }
        
        # Добавляем процентили
        sorted_times = sorted(self.request_times)
        summary["p50_request_time"] = round(sorted_times[int(len(sorted_times) * 0.5)], 3) if self.request_times else 0
        summary["p90_request_time"] = round(sorted_times[int(len(sorted_times) * 0.9)], 3) if self.request_times else 0
        summary["p95_request_time"] = round(sorted_times[int(len(sorted_times) * 0.95)], 3) if self.request_times else 0
        summary["p99_request_time"] = round(sorted_times[int(len(sorted_times) * 0.99)], 3) if self.request_times else 0
        
        return summary
    
    def save_to_file(self, filename: str) -> None:
        """Сохранение результатов в файл"""
        with open(filename, 'w') as f:
            json.dump({
                "summary": self.get_summary(),
                "requests": self.request_details
            }, f, indent=2)
        
        logger.info(f"Результаты сохранены в файл: {filename}")


@pytest.fixture
async def load_test_results() -> LoadTestResults:
    """Фикстура, предоставляющая объект для сбора результатов тестирования"""
    return LoadTestResults()

@pytest.fixture
async def authenticated_session() -> Tuple[aiohttp.ClientSession, str, str]:
    """Создает аутентифицированную сессию aiohttp с токенами"""
    session = aiohttp.ClientSession()
    
    # Авторизация
    auth_response = await session.post(
        f"{API_URL}/api/v1/users/login",
        json={
            "email": AUTH_EMAIL,
            "password": AUTH_PASSWORD
        }
    )
    
    if auth_response.status != 200:
        await session.close()
        pytest.skip(f"Не удалось авторизоваться: {auth_response.status}")
        return None, None, None
    
    auth_data = await auth_response.json()
    access_token = auth_data.get("access_token")
    user_id = auth_data.get("user", {}).get("id")
    
    # Получение токена Centrifugo
    token_response = await session.post(
        f"{API_URL}/api/v1/centrifugo/token",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    if token_response.status != 200:
        await session.close()
        pytest.skip(f"Не удалось получить токен Centrifugo: {token_response.status}")
        return None, None, None
    
    token_data = await token_response.json()
    centrifugo_token = token_data.get("token")
    
    # Настраиваем сессию с токеном авторизации
    session.headers.update({"Authorization": f"Bearer {access_token}"})
    
    try:
        yield session, access_token, centrifugo_token
    finally:
        await session.close()

@pytest.fixture
async def test_chat_for_load(authenticated_session) -> Optional[str]:
    """Создает тестовый чат для нагрузочного тестирования"""
    session, access_token, _ = authenticated_session
    if not session or not access_token:
        return None
    
    # Попытка создания нового чата
    try:
        response = await session.post(
            f"{API_URL}/api/v1/chats",
            json={
                "name": f"Load Test Chat {datetime.now().isoformat()}",
                "is_private": False
            }
        )
        
        if response.status in (200, 201):
            data = await response.json()
            chat_id = data.get("id")
            if chat_id:
                return chat_id
            
        # Если не удалось создать новый, используем существующий
        response = await session.get(f"{API_URL}/api/v1/chats")
        if response.status == 200:
            data = await response.json()
            chats = data.get("items", [])
            if chats:
                return chats[0].get("id")
    except Exception as e:
        logger.error(f"Ошибка при создании тестового чата: {str(e)}")
    
    return None 