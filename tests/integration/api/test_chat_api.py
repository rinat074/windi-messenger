"""
Интеграционные тесты для API чатов
"""
import pytest
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger("integration_tests")

@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_creation_and_retrieval(auth_token, auth_headers):
    """Тест создания и получения чата через API"""
    import httpx
    
    if not auth_token or not auth_headers:
        pytest.skip("Нет токена авторизации")
    
    # Генерируем уникальное имя чата
    chat_name = f"Integration Test Chat {datetime.now().isoformat()}"
    
    try:
        # 1. Создаем новый чат
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{pytest.API_URL}/api/v1/chats",
                headers=auth_headers,
                json={
                    "name": chat_name,
                    "is_private": False
                },
                timeout=10.0
            )
            
            assert response.status_code in (200, 201), f"Ошибка создания чата: {response.status_code} {response.text}"
            
            chat_data = response.json()
            chat_id = chat_data.get("id")
            
            assert chat_id is not None, "ID чата отсутствует в ответе"
            assert chat_data.get("name") == chat_name, "Имя чата в ответе не соответствует созданному"
            
            logger.info(f"Создан чат с ID: {chat_id}")
            
            # 2. Получаем список чатов и проверяем наличие созданного
            response = await client.get(
                f"{pytest.API_URL}/api/v1/chats",
                headers=auth_headers,
                timeout=10.0
            )
            
            assert response.status_code == 200, f"Ошибка получения списка чатов: {response.status_code} {response.text}"
            
            chats_data = response.json()
            chats = chats_data.get("items", [])
            
            # Ищем созданный чат в списке
            found = False
            for chat in chats:
                if chat.get("id") == chat_id:
                    found = True
                    assert chat.get("name") == chat_name, "Имя чата в списке не соответствует созданному"
                    break
            
            assert found, f"Созданный чат с ID {chat_id} не найден в списке чатов"
            
            # 3. Получаем информацию о конкретном чате
            response = await client.get(
                f"{pytest.API_URL}/api/v1/chats/{chat_id}",
                headers=auth_headers,
                timeout=10.0
            )
            
            assert response.status_code == 200, f"Ошибка получения информации о чате: {response.status_code} {response.text}"
            
            chat_info = response.json()
            assert chat_info.get("id") == chat_id, "ID чата в ответе не соответствует запрошенному"
            assert chat_info.get("name") == chat_name, "Имя чата в ответе не соответствует созданному"
            
            logger.info(f"Тест успешно завершен для чата {chat_id}")
    
    except Exception as e:
        logger.error(f"Ошибка в тесте: {str(e)}")
        raise


@pytest.mark.integration
@pytest.mark.asyncio
async def test_message_sending_and_history(auth_token, auth_headers, test_chat_id, test_message_data, create_test_message, get_message_history):
    """Тест отправки сообщения и получения истории"""
    import httpx
    
    if not auth_token or not auth_headers or not test_chat_id:
        pytest.skip("Отсутствуют необходимые данные")
    
    try:
        # 1. Отправляем сообщение в чат
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{pytest.API_URL}/api/v1/centrifugo/publish?chat_id={test_chat_id}",
                headers=auth_headers,
                json=test_message_data,
                timeout=10.0
            )
            
            assert response.status_code == 200, f"Ошибка отправки сообщения: {response.status_code} {response.text}"
            
            message_data = response.json()
            message_id = message_data.get("id")
            
            assert message_id is not None, "ID сообщения отсутствует в ответе"
            assert message_data.get("text") == test_message_data["text"], "Текст сообщения в ответе не соответствует отправленному"
            assert message_data.get("client_message_id") == test_message_data["client_message_id"], "client_message_id в ответе не соответствует отправленному"
            
            logger.info(f"Отправлено сообщение с ID: {message_id}")
            
            # Ждем обработки сообщения
            await asyncio.sleep(1)
            
            # 2. Получаем историю сообщений и проверяем наличие отправленного
            response = await client.get(
                f"{pytest.API_URL}/api/v1/chats/{test_chat_id}/messages",
                headers=auth_headers,
                params={"limit": 20},
                timeout=10.0
            )
            
            assert response.status_code == 200, f"Ошибка получения истории сообщений: {response.status_code} {response.text}"
            
            history_data = response.json()
            messages = history_data.get("items", [])
            
            # Ищем отправленное сообщение в истории
            found = False
            for msg in messages:
                if msg.get("id") == message_id:
                    found = True
                    assert msg.get("text") == test_message_data["text"], "Текст сообщения в истории не соответствует отправленному"
                    assert msg.get("client_message_id") == test_message_data["client_message_id"], "client_message_id в истории не соответствует отправленному"
                    break
            
            assert found, f"Отправленное сообщение с ID {message_id} не найдено в истории чата"
            
            logger.info(f"Тест успешно завершен для сообщения {message_id}")
    
    except Exception as e:
        logger.error(f"Ошибка в тесте: {str(e)}")
        raise 