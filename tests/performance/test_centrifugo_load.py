"""
Нагрузочное тестирование для Centrifugo
"""
import os
import sys
import time
import json
import asyncio
import logging
import argparse
import uuid
import aiohttp
import pytest
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any, Tuple

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("centrifugo_load_test.log")
    ]
)
logger = logging.getLogger("centrifugo_load_test")

# Загрузка переменных окружения
load_dotenv()

# Константы
API_URL = os.getenv("API_URL", "http://localhost:8000")
CENTRIFUGO_URL = os.getenv("CENTRIFUGO_URL", "http://localhost:8001")
CENTRIFUGO_WS_URL = os.getenv("CENTRIFUGO_WS_URL", "ws://localhost:8001/connection/websocket")
AUTH_EMAIL = os.getenv("TEST_USER_EMAIL", "admin@example.com")
AUTH_PASSWORD = os.getenv("TEST_USER_PASSWORD", "password123")


class LoadTestResults:
    """Класс для сбора и анализа результатов нагрузочного тестирования"""
    
    def __init__(self):
        self.request_times = []  # Список времен выполнения запросов
        self.error_count = 0     # Счетчик ошибок
        self.success_count = 0   # Счетчик успешных запросов
        self.start_time = None   # Время начала теста
        self.end_time = None     # Время окончания теста
        self.request_details = []  # Детали каждого запроса
    
    def start(self):
        """Начало тестирования"""
        self.start_time = time.time()
    
    def end(self):
        """Окончание тестирования"""
        self.end_time = time.time()
    
    def add_request(self, duration: float, success: bool, details: Dict[str, Any] = None):
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
    
    def save_to_file(self, filename: str):
        """Сохранение результатов в файл"""
        with open(filename, 'w') as f:
            json.dump({
                "summary": self.get_summary(),
                "requests": self.request_details
            }, f, indent=2)
        
        logger.info(f"Результаты сохранены в файл: {filename}")


class CentrifugoLoadTester:
    """Класс для выполнения нагрузочного тестирования Centrifugo"""
    
    def __init__(self, 
                 api_url: str, 
                 centrifugo_url: str, 
                 centrifugo_ws_url: str,
                 auth_email: str, 
                 auth_password: str):
        self.api_url = api_url
        self.centrifugo_url = centrifugo_url
        self.centrifugo_ws_url = centrifugo_ws_url
        self.auth_email = auth_email
        self.auth_password = auth_password
        self.access_token = None
        self.centrifugo_token = None
        self.user_id = None
        self.chat_id = None
    
    async def setup(self):
        """Настройка тестового окружения"""
        # Авторизация и получение токенов
        await self.authenticate()
        await self.get_centrifugo_token()
        
        # Создание тестового чата или получение существующего
        await self.setup_test_chat()
    
    async def authenticate(self):
        """Авторизация пользователя и получение токена доступа"""
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{self.api_url}/api/v1/users/login",
                    json={
                        "email": self.auth_email,
                        "password": self.auth_password
                    }
                )
                
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Ошибка авторизации: {response.status} {text}")
                
                data = await response.json()
                self.access_token = data.get("access_token")
                self.user_id = data.get("user", {}).get("id")
                
                if not self.access_token or not self.user_id:
                    raise Exception("Не удалось получить токен доступа или ID пользователя")
                
                logger.info(f"Успешная авторизация пользователя {self.auth_email}")
        except Exception as e:
            logger.error(f"Ошибка при авторизации: {str(e)}")
            raise
    
    async def get_centrifugo_token(self):
        """Получение токена для подключения к Centrifugo"""
        if not self.access_token:
            raise Exception("Необходимо сначала авторизоваться")
        
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{self.api_url}/api/v1/centrifugo/token",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Ошибка получения токена Centrifugo: {response.status} {text}")
                
                data = await response.json()
                self.centrifugo_token = data.get("token")
                
                if not self.centrifugo_token:
                    raise Exception("Не удалось получить токен Centrifugo")
                
                logger.info("Успешно получен токен Centrifugo")
        except Exception as e:
            logger.error(f"Ошибка при получении токена Centrifugo: {str(e)}")
            raise
    
    async def setup_test_chat(self):
        """Создание или получение тестового чата"""
        if not self.access_token:
            raise Exception("Необходимо сначала авторизоваться")
        
        try:
            # Пытаемся получить список существующих чатов
            async with aiohttp.ClientSession() as session:
                response = await session.get(
                    f"{self.api_url}/api/v1/chats",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                
                if response.status == 200:
                    data = await response.json()
                    chats = data.get("items", [])
                    
                    if chats:
                        # Используем первый доступный чат
                        self.chat_id = chats[0].get("id")
                        logger.info(f"Использование существующего чата: {self.chat_id}")
                        return
                
                # Если не удалось получить существующий чат, создаем новый
                response = await session.post(
                    f"{self.api_url}/api/v1/chats",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "name": f"Load Test Chat {datetime.now().isoformat()}",
                        "is_private": False
                    }
                )
                
                if response.status != 201 and response.status != 200:
                    text = await response.text()
                    raise Exception(f"Ошибка создания тестового чата: {response.status} {text}")
                
                data = await response.json()
                self.chat_id = data.get("id")
                
                if not self.chat_id:
                    raise Exception("Не удалось получить ID созданного чата")
                
                logger.info(f"Создан новый тестовый чат: {self.chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при настройке тестового чата: {str(e)}")
            raise
    
    async def send_message(self, text: str = None) -> Tuple[bool, float, Dict[str, Any]]:
        """Отправка тестового сообщения в чат"""
        if not self.access_token or not self.chat_id:
            raise Exception("Необходимо сначала выполнить настройку")
        
        message_text = text or f"Test message {uuid.uuid4()}"
        client_message_id = f"load-test-{uuid.uuid4()}"
        details = {}
        
        start_time = time.time()
        success = False
        
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{self.api_url}/api/v1/centrifugo/publish?chat_id={self.chat_id}",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": message_text,
                        "client_message_id": client_message_id
                    }
                )
                
                end_time = time.time()
                duration = end_time - start_time
                
                details["status_code"] = response.status
                
                if response.status == 200:
                    data = await response.json()
                    details["message_id"] = data.get("id")
                    success = True
                else:
                    text = await response.text()
                    details["error"] = text
                    success = False
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            details["error"] = str(e)
            success = False
        
        return success, duration, details
    
    async def request_token(self) -> Tuple[bool, float, Dict[str, Any]]:
        """Тест запроса токена Centrifugo"""
        if not self.access_token:
            raise Exception("Необходимо сначала авторизоваться")
        
        details = {}
        
        start_time = time.time()
        success = False
        
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{self.api_url}/api/v1/centrifugo/token",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                
                end_time = time.time()
                duration = end_time - start_time
                
                details["status_code"] = response.status
                
                if response.status == 200:
                    data = await response.json()
                    details["token"] = data.get("token") is not None
                    success = True
                else:
                    text = await response.text()
                    details["error"] = text
                    success = False
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            details["error"] = str(e)
            success = False
        
        return success, duration, details
    
    async def get_presence(self) -> Tuple[bool, float, Dict[str, Any]]:
        """Тест запроса информации о присутствующих в чате"""
        if not self.access_token or not self.chat_id:
            raise Exception("Необходимо сначала выполнить настройку")
        
        details = {}
        
        start_time = time.time()
        success = False
        
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(
                    f"{self.api_url}/api/v1/centrifugo/presence/{self.chat_id}",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                
                end_time = time.time()
                duration = end_time - start_time
                
                details["status_code"] = response.status
                
                if response.status == 200:
                    data = await response.json()
                    details["clients_count"] = len(data.get("clients", {}))
                    success = True
                else:
                    text = await response.text()
                    details["error"] = text
                    success = False
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            details["error"] = str(e)
            success = False
        
        return success, duration, details
    
    async def run_load_test(self, 
                           request_type: str, 
                           num_requests: int, 
                           concurrency: int) -> LoadTestResults:
        """Запуск нагрузочного тестирования"""
        results = LoadTestResults()
        results.start()
        
        # Выбор функции для тестирования в зависимости от типа
        if request_type == "publish":
            test_function = self.send_message
        elif request_type == "token":
            test_function = self.request_token
        elif request_type == "presence":
            test_function = self.get_presence
        else:
            raise ValueError(f"Неизвестный тип запроса: {request_type}")
        
        logger.info(f"Запуск нагрузочного теста: {request_type}, {num_requests} запросов, {concurrency} одновременных")
        
        # Создаем пул задач для одновременного выполнения
        tasks = []
        for i in range(num_requests):
            tasks.append(test_function())
        
        # Выполняем задачи с ограничением одновременно выполняемых
        completed_tasks = 0
        for i in range(0, len(tasks), concurrency):
            batch = tasks[i:i+concurrency]
            results_batch = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in results_batch:
                completed_tasks += 1
                if isinstance(result, Exception):
                    logger.error(f"Ошибка выполнения запроса: {str(result)}")
                    results.add_request(0.0, False, {"error": str(result)})
                else:
                    success, duration, details = result
                    results.add_request(duration, success, details)
                
                # Выводим прогресс каждые 10% запросов
                if completed_tasks % max(1, num_requests // 10) == 0 or completed_tasks == num_requests:
                    logger.info(f"Прогресс: {completed_tasks}/{num_requests} запросов ({completed_tasks/num_requests*100:.1f}%)")
        
        results.end()
        
        # Выводим сводку результатов
        summary = results.get_summary()
        logger.info("Результаты нагрузочного тестирования:")
        for key, value in summary.items():
            logger.info(f"{key}: {value}")
        
        return results


@pytest.mark.asyncio
@pytest.mark.parametrize("request_type", ["publish", "token", "presence"])
@pytest.mark.parametrize("concurrency", [1, 5, 10])
async def test_centrifugo_load(request_type, concurrency):
    """Параметризованный тест для различных типов запросов и уровней конкурентности"""
    # Настройка тестера
    tester = CentrifugoLoadTester(
        api_url=API_URL,
        centrifugo_url=CENTRIFUGO_URL,
        centrifugo_ws_url=CENTRIFUGO_WS_URL,
        auth_email=AUTH_EMAIL,
        auth_password=AUTH_PASSWORD
    )
    
    # Инициализация
    await tester.setup()
    
    # Запуск теста с небольшим количеством запросов для CI
    num_requests = 20  # Небольшое количество для CI
    
    # Запуск теста и получение результатов
    results = await tester.run_load_test(request_type, num_requests, concurrency)
    
    # Проверка результатов
    summary = results.get_summary()
    assert summary["success_rate"] > 90, f"Низкий показатель успешных запросов: {summary['success_rate']}%"
    
    # Сохраняем результаты в файл
    results.save_to_file(f"load_test_{request_type}_c{concurrency}.json")


async def main():
    """Основная функция для запуска из командной строки"""
    parser = argparse.ArgumentParser(description="Нагрузочное тестирование Centrifugo")
    parser.add_argument("--type", choices=["publish", "token", "presence"], default="publish",
                       help="Тип запроса для тестирования")
    parser.add_argument("--requests", type=int, default=100,
                       help="Количество запросов для выполнения")
    parser.add_argument("--concurrency", type=int, default=10,
                       help="Количество одновременных запросов")
    parser.add_argument("--api-url", default=API_URL,
                       help="URL API сервера")
    parser.add_argument("--centrifugo-url", default=CENTRIFUGO_URL,
                       help="URL Centrifugo HTTP API")
    parser.add_argument("--centrifugo-ws-url", default=CENTRIFUGO_WS_URL,
                       help="URL Centrifugo WebSocket")
    parser.add_argument("--email", default=AUTH_EMAIL,
                       help="Email для авторизации")
    parser.add_argument("--password", default=AUTH_PASSWORD,
                       help="Пароль для авторизации")
    parser.add_argument("--output", default="load_test_results.json",
                       help="Файл для сохранения результатов")
    
    args = parser.parse_args()
    
    # Настройка тестера
    tester = CentrifugoLoadTester(
        api_url=args.api_url,
        centrifugo_url=args.centrifugo_url,
        centrifugo_ws_url=args.centrifugo_ws_url,
        auth_email=args.email,
        auth_password=args.password
    )
    
    # Инициализация
    await tester.setup()
    
    # Запуск теста и получение результатов
    results = await tester.run_load_test(
        request_type=args.type,
        num_requests=args.requests,
        concurrency=args.concurrency
    )
    
    # Сохраняем результаты в файл
    results.save_to_file(args.output)


if __name__ == "__main__":
    asyncio.run(main()) 