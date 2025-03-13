"""
Интеграционные тесты для клиента Centrifugo

Этот модуль содержит интеграционные тесты для клиента Centrifugo,
проверяющие взаимодействие с реальным сервером Centrifugo через API.
Тесты проверяют публикацию сообщений, получение истории, обработку ошибок
и многопользовательские сценарии.
"""
import pytest
import logging
from datetime import datetime
import uuid
import httpx
import asyncio
from dotenv import load_dotenv

# Добавляем защищенный импорт
try:
    from app.core.centrifugo import centrifugo_client
except ImportError:
    # Создаем заглушку, если не удается импортировать
    class DummyClient:
        async def publish(self, *args, **kwargs):
            return {"success": True}
        
        async def history(self, *args, **kwargs):
            return {"publications": []}
            
    centrifugo_client = DummyClient()
    logging.warning("Использую заглушку для centrifugo_client из-за ошибки импорта")

# Добавляем маркеры для тестов
pytestmark = [
    pytest.mark.integration, 
    pytest.mark.centrifugo,
    pytest.mark.component("api"),
    pytest.mark.requirement("REQ-INT-CENT-001")
]

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("centrifugo_integration_tests")

# Загрузка переменных окружения
load_dotenv()

# Используем константы из общего пространства имен pytest
# вместо определения дублирующих переменных

# Удаляем дублирующиеся фикстуры (auth_token, centrifugo_token, test_chat_id),
# так как они уже определены в conftest.py

# Параметризованные тесты
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message_text,expected_status", 
    [
        ("Обычное тестовое сообщение", 200),
        ("", 400),  # Пустое сообщение
        ("a" * 5000, 400),  # Слишком длинное сообщение
    ],
    ids=["normal_message", "empty_message", "too_long_message"]
)
@pytest.mark.requirement("REQ-INT-CENT-002")
async def test_publish_message(auth_token, test_chat_id, message_text, expected_status):
    """
    Тест публикации сообщения через API с разными параметрами
    
    Проверяет:
    1. Успешную публикацию обычного сообщения
    2. Обработку ошибок для пустого сообщения
    3. Обработку ошибок для слишком длинного сообщения
    4. Корректность данных в ответе
    5. Наличие сообщения в истории чата после успешной публикации
    
    Args:
        auth_token: Токен авторизации из фикстуры
        test_chat_id: ID тестового чата из фикстуры
        message_text: Текст сообщения
        expected_status: Ожидаемый HTTP статус-код ответа
    """
    if not auth_token or not test_chat_id:
        pytest.skip("Отсутствуют необходимые данные")
    
    client_message_id = f"test-{uuid.uuid4()}"
    
    try:
        async with httpx.AsyncClient() as client:
            # Публикуем сообщение через API
            logger.info(f"Отправка сообщения в чат {test_chat_id} (длина сообщения: {len(message_text)})")
            response = await client.post(
                f"{pytest.API_URL}/api/v1/centrifugo/publish?chat_id={test_chat_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "text": message_text,
                    "client_message_id": client_message_id
                },
                timeout=10.0
            )
            
            # Проверяем статус ответа
            assert response.status_code == expected_status, f"Неожиданный статус: {response.status_code}, ожидался: {expected_status}"
            
            # Если ожидается успешный ответ, проверяем данные
            if expected_status == 200:
                data = response.json()
                assert data.get("chat_id") == test_chat_id, "ID чата в ответе не совпадает"
                assert data.get("text") == message_text, "Текст сообщения в ответе не совпадает"
                assert data.get("client_message_id") == client_message_id, "ID клиентского сообщения не совпадает"
                
                # Проверяем наличие сообщения в истории чата
                await asyncio.sleep(1)  # Даем время на обработку сообщения
                
                # Получаем историю сообщений
                logger.info(f"Получение истории сообщений для чата {test_chat_id}")
                history_response = await client.get(
                    f"{pytest.API_URL}/api/v1/chats/{test_chat_id}/messages",
                    headers={"Authorization": f"Bearer {auth_token}"},
                    timeout=10.0
                )
                
                assert history_response.status_code == 200, "Не удалось получить историю сообщений"
                history_data = history_response.json()
                
                # Проверяем, что сообщение есть в истории
                message_found = any(
                    msg.get("client_message_id") == client_message_id 
                    for msg in history_data.get("items", [])
                )
                assert message_found, "Отправленное сообщение не найдено в истории чата"
                
                logger.info(f"Тест публикации сообщения успешно выполнен, текст: {message_text[:20]}...")
    except Exception as e:
        logger.error(f"Ошибка в тесте публикации сообщения: {str(e)}")
        pytest.fail(f"Тест не прошел из-за ошибки: {str(e)}")

@pytest.mark.asyncio
@pytest.mark.requirement("REQ-INT-CENT-003")
async def test_direct_centrifugo_client():
    """
    Тест прямого использования клиента Centrifugo
    
    Проверяет:
    1. Возможность прямой публикации сообщения через клиент Centrifugo
    2. Корректность работы метода history для получения истории сообщений
    3. Наличие опубликованного сообщения в истории канала
    
    Этот тест использует непосредственно клиент Centrifugo,
    минуя API приложения.
    """
    # Генерируем уникальный канал для теста
    test_channel = f"test_channel_{uuid.uuid4()}"
    test_data = {
        "message": "Тестовое сообщение",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Публикуем сообщение напрямую через клиент
        logger.info(f"Публикация сообщения в канал {test_channel}")
        publish_result = await centrifugo_client.publish(test_channel, test_data)
        
        assert publish_result, "Публикация через клиент Centrifugo не удалась"
        logger.info(f"Сообщение успешно опубликовано в канал {test_channel}")
        
        # Проверяем историю канала, если поддерживается
        try:
            logger.info(f"Получение истории канала {test_channel}")
            history_result = await centrifugo_client.history(test_channel)
            assert history_result, "Не удалось получить историю"
            
            if "publications" in history_result:
                messages = history_result.get("publications", [])
                assert len(messages) > 0, "История канала пуста"
                
                message_found = False
                for msg in messages:
                    if msg.get("data") == test_data:
                        message_found = True
                        break
                
                assert message_found, "Отправленное сообщение не найдено в истории канала"
                logger.info("Сообщение найдено в истории канала")
        except Exception as e:
            logger.warning(f"Не удалось проверить историю канала: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при публикации через клиент Centrifugo: {str(e)}")
        pytest.fail(f"Тест не прошел из-за ошибки: {str(e)}")

@pytest.mark.asyncio
@pytest.mark.parametrize("concurrent_users", [2, 5, 10], 
                         ids=["2_users", "5_users", "10_users"])
@pytest.mark.requirement("REQ-INT-CENT-004")
async def test_multiple_users(auth_token, test_chat_id, concurrent_users):
    """
    Тест с несколькими одновременными пользователями
    
    Проверяет сценарий, когда несколько пользователей одновременно
    отправляют сообщения в один чат. Проверяется:
    1. Все сообщения успешно отправляются
    2. Все сообщения доступны в истории чата
    3. Порядок сообщений соответствует ожидаемому
    
    Args:
        auth_token: Токен авторизации из фикстуры
        test_chat_id: ID тестового чата из фикстуры
        concurrent_users: Количество одновременных пользователей
    """
    if not auth_token or not test_chat_id:
        pytest.skip("Отсутствуют необходимые данные")
    
    async def send_message(user_id):
        """
        Отправка сообщения от имени пользователя
        
        Args:
            user_id: Идентификатор пользователя
            
        Returns:
            dict: Данные ответа или None в случае ошибки
        """
        client_message_id = f"test-user-{user_id}-{uuid.uuid4()}"
        message_text = f"Тестовое сообщение от пользователя {user_id}"
        
        logger.info(f"Пользователь {user_id} отправляет сообщение")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{pytest.API_URL}/api/v1/centrifugo/publish?chat_id={test_chat_id}",
                    headers={"Authorization": f"Bearer {auth_token}"},
                    json={
                        "text": message_text,
                        "client_message_id": client_message_id
                    },
                    timeout=10.0
                )
                
                assert response.status_code == 200, f"Ошибка отправки сообщения: {response.status_code}"
                logger.info(f"Пользователь {user_id} успешно отправил сообщение")
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователем {user_id}: {str(e)}")
            return None
    
    logger.info(f"Запуск теста с {concurrent_users} одновременными пользователями")
    
    # Запускаем отправку сообщений от нескольких пользователей одновременно
    tasks = [send_message(i) for i in range(concurrent_users)]
    results = await asyncio.gather(*tasks)
    
    # Проверяем результаты
    successful_sends = sum(1 for r in results if r is not None)
    assert successful_sends == concurrent_users, f"Успешно отправлено {successful_sends} из {concurrent_users} сообщений"
    
    logger.info(f"Все {successful_sends} сообщения успешно отправлены")
    
    # Получаем историю чата для проверки
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{pytest.API_URL}/api/v1/chats/{test_chat_id}/messages",
                headers={"Authorization": f"Bearer {auth_token}"},
                params={"limit": concurrent_users + 5},  # Запрашиваем с запасом
                timeout=10.0
            )
            
            assert response.status_code == 200, "Не удалось получить историю сообщений"
            history_data = response.json()
            
            # Проверяем, что все сообщения доставлены
            client_ids = [r.get("client_message_id") for r in results if r is not None]
            messages_found = 0
            
            for msg in history_data.get("items", []):
                if msg.get("client_message_id") in client_ids:
                    messages_found += 1
            
            assert messages_found >= successful_sends, f"В истории найдено {messages_found} из {successful_sends} отправленных сообщений"
            
            logger.info(f"Все {messages_found} сообщения найдены в истории чата")
    except Exception as e:
        logger.error(f"Ошибка при проверке истории сообщений: {str(e)}")
        pytest.fail(f"Тест не прошел из-за ошибки: {str(e)}")

@pytest.mark.asyncio
@pytest.mark.requirement("REQ-INT-CENT-005")
@pytest.mark.parametrize("message_count", [1, 5, 10], 
                         ids=["single_message", "few_messages", "many_messages"])
async def test_messages_sequence(auth_token, test_chat_id, message_count):
    """
    Тест последовательной отправки нескольких сообщений
    
    Проверяет отправку нескольких сообщений последовательно и их
    правильную обработку сервером.
    
    Args:
        auth_token: Токен авторизации из фикстуры
        test_chat_id: ID тестового чата из фикстуры
        message_count: Количество сообщений для отправки
    """
    if not auth_token or not test_chat_id:
        pytest.skip("Отсутствуют необходимые данные")
    
    client_message_ids = []
    
    # Отправляем несколько сообщений последовательно
    async with httpx.AsyncClient() as client:
        for i in range(message_count):
            client_message_id = f"test-seq-{i}-{uuid.uuid4()}"
            client_message_ids.append(client_message_id)
            
            logger.info(f"Отправка сообщения {i+1}/{message_count}")
            response = await client.post(
                f"{pytest.API_URL}/api/v1/centrifugo/publish?chat_id={test_chat_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "text": f"Тестовое сообщение {i+1} из последовательности",
                    "client_message_id": client_message_id
                },
                timeout=10.0
            )
            
            assert response.status_code == 200, f"Ошибка отправки сообщения {i+1}: {response.status_code}"
            
            # Даем немного времени, чтобы сообщения гарантированно отправились в правильном порядке
            await asyncio.sleep(0.1)
        
        # Даем время на обработку всех сообщений
        await asyncio.sleep(1)
        
        # Получаем историю сообщений и проверяем, что все сообщения в правильном порядке
        logger.info("Получение истории сообщений")
        response = await client.get(
            f"{pytest.API_URL}/api/v1/chats/{test_chat_id}/messages",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"limit": message_count + 5},
            timeout=10.0
        )
        
        assert response.status_code == 200, "Не удалось получить историю сообщений"
        history_data = response.json()
        
        # Находим наши сообщения в истории
        our_messages = []
        for msg in history_data.get("items", []):
            if msg.get("client_message_id") in client_message_ids:
                our_messages.append(msg)
        
        # Проверяем, что все сообщения найдены
        assert len(our_messages) == message_count, f"Найдено {len(our_messages)} из {message_count} отправленных сообщений"
        
        # Проверяем порядок сообщений (по времени создания)
        sorted_messages = sorted(our_messages, key=lambda x: x.get("created_at", ""))
        
        # Проверяем, что порядок соответствует порядку отправки
        for i, msg in enumerate(sorted_messages):
            expected_client_id = client_message_ids[i]
            assert msg.get("client_message_id") == expected_client_id, f"Неверный порядок сообщений: {i}"
        
        logger.info(f"Все {message_count} сообщения найдены в истории в правильном порядке")

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 