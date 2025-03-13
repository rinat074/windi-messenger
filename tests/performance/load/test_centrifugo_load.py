"""
Нагрузочное тестирование для Centrifugo
"""
import os
import time
import asyncio
import logging
import uuid
import pytest
from typing import Dict, Any, Tuple

# Добавляем маркеры для тестов
pytestmark = [pytest.mark.performance, pytest.mark.slow]

logger = logging.getLogger("load_tests")

class CentrifugoLoadTest:
    """Класс для выполнения нагрузочного тестирования Centrifugo"""
    
    def __init__(self, session, access_token, centrifugo_token, chat_id=None):
        self.session = session
        self.access_token = access_token
        self.centrifugo_token = centrifugo_token
        self.chat_id = chat_id
        self.base_url = os.getenv("API_URL", "http://localhost:8000")
    
    async def send_message(self, text: str = None) -> Tuple[bool, float, Dict[str, Any]]:
        """Отправка тестового сообщения в чат"""
        if not self.access_token or not self.chat_id:
            raise ValueError("Нет токена доступа или ID чата")
        
        message_text = text or f"Test message {uuid.uuid4()}"
        client_message_id = f"load-test-{uuid.uuid4()}"
        details = {}
        
        start_time = time.time()
        success = False
        
        try:
            response = await self.session.post(
                f"{self.base_url}/api/v1/centrifugo/publish?chat_id={self.chat_id}",
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
            raise ValueError("Нет токена доступа")
        
        details = {}
        
        start_time = time.time()
        success = False
        
        try:
            response = await self.session.post(
                f"{self.base_url}/api/v1/centrifugo/token"
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
            raise ValueError("Нет токена доступа или ID чата")
        
        details = {}
        
        start_time = time.time()
        success = False
        
        try:
            response = await self.session.get(
                f"{self.base_url}/api/v1/centrifugo/presence/{self.chat_id}"
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
                           concurrency: int,
                           results) -> None:
        """Запуск нагрузочного тестирования"""
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


@pytest.mark.asyncio
@pytest.mark.parametrize("request_type", ["publish", "token", "presence"])
@pytest.mark.parametrize("concurrency", [1, 5, 10])
async def test_centrifugo_load(request_type, concurrency, authenticated_session, test_chat_for_load, load_test_results):
    """Параметризованный тест для различных типов запросов и уровней конкурентности"""
    # Пропускаем тест, если не удалось получить необходимые данные
    if not authenticated_session or not test_chat_for_load:
        pytest.skip("Не удалось получить необходимые данные для теста")
    
    session, access_token, centrifugo_token = authenticated_session
    
    # Настройка тестера
    load_tester = CentrifugoLoadTest(
        session=session,
        access_token=access_token,
        centrifugo_token=centrifugo_token,
        chat_id=test_chat_for_load
    )
    
    # Запуск теста с небольшим количеством запросов для CI
    num_requests = 20  # Небольшое количество для CI
    
    if "FULL_LOAD_TEST" in os.environ:
        num_requests = 100  # Увеличиваем для полного нагрузочного теста
    
    # Запуск теста и получение результатов
    await load_tester.run_load_test(request_type, num_requests, concurrency, load_test_results)
    
    # Проверка результатов
    summary = load_test_results.get_summary()
    assert summary["success_rate"] > 90, f"Низкий показатель успешных запросов: {summary['success_rate']}%"
    
    # Сохраняем результаты в файл
    filename = f"load_test_{request_type}_c{concurrency}.json"
    load_test_results.save_to_file(filename) 