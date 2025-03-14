#!/usr/bin/env python
"""
Скрипт для тестирования интеграции с Centrifugo

Этот скрипт проверяет:
1. Подключение к Centrifugo
2. Аутентификацию пользователя
3. Публикацию сообщений
4. Получение истории сообщений
5. Проверку присутствия пользователей в каналах

Использование:
    python scripts/test_centrifugo_integration.py [--verbose] [--no-cleanup]

Параметры:
    --verbose: Включает подробное логирование
    --no-cleanup: Не удаляет тестовые данные после выполнения
"""

import os
import sys
import json
import uuid
import asyncio
import logging
import argparse
from typing import Dict, Any, Optional
from datetime import datetime

import httpx
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("centrifugo_integration_test")

# Загрузка переменных окружения
load_dotenv()

# Константы
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
CENTRIFUGO_URL = os.getenv("CENTRIFUGO_URL", "http://localhost:8001")
TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL", "test@example.com")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "password")

# Глобальные переменные для хранения тестовых данных
test_data = {
    "auth_token": None,
    "centrifugo_token": None,
    "test_chat_id": None,
    "test_messages": []
}


async def get_auth_token() -> Optional[str]:
    """Получение токена авторизации"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/auth/login",
                json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info("Успешная авторизация")
                return data.get("access_token")
            else:
                logger.error(f"Ошибка авторизации: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса авторизации: {str(e)}")
        return None


async def get_centrifugo_token(auth_token: str) -> Optional[str]:
    """Получение токена Centrifugo"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_URL}/centrifugo/token",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info("Получен токен Centrifugo")
                return data.get("token")
            else:
                logger.error(f"Ошибка получения токена Centrifugo: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса токена Centrifugo: {str(e)}")
        return None


async def get_user_chats(auth_token: str) -> Optional[list]:
    """Получение списка чатов пользователя"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_URL}/chats",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            if response.status_code == 200:
                chats = response.json()
                logger.info(f"Получено {len(chats)} чатов")
                return chats
            else:
                logger.error(f"Ошибка получения чатов: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса чатов: {str(e)}")
        return None


async def send_message(auth_token: str, channel: str, text: str) -> Optional[Dict[str, Any]]:
    """Отправка сообщения через API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/centrifugo/publish",
                params={"channel": channel},
                json={"text": text, "type": "message"},
                headers={
                    "Authorization": f"Bearer {auth_token}",
                    "Content-Type": "application/json"
                },
                timeout=10.0  # Увеличиваем таймаут для надежности
            )
            
            if response.status_code == 200:
                message = response.json()
                logger.info(f"Отправлено сообщение в канал {channel}: {text}")
                return message
            else:
                logger.error(f"Ошибка при отправке сообщения: {response.status_code} - {response.text}")
                return None
    except httpx.TimeoutException:
        logger.error(f"Таймаут при отправке сообщения в канал {channel}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса отправки сообщения: {str(e)}")
        return None
    finally:
        # Явно закрываем клиент для освобождения ресурсов
        if 'client' in locals():
            await client.aclose()


async def check_message_history(auth_token: str, chat_id: str) -> Optional[list]:
    """Проверка истории сообщений чата"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_URL}/chats/{chat_id}/messages",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            if response.status_code == 200:
                messages = response.json()
                logger.info(f"Получено {len(messages)} сообщений из чата {chat_id}")
                return messages
            else:
                logger.error(f"Ошибка получения истории сообщений: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса истории сообщений: {str(e)}")
        return None
    finally:
        # Явно закрываем клиент для освобождения ресурсов
        if 'client' in locals():
            await client.aclose()


async def check_presence(auth_token: str, channel: str) -> Optional[Dict[str, Any]]:
    """Проверка присутствия пользователей в канале"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_URL}/centrifugo/presence/{channel}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            if response.status_code == 200:
                presence_data = response.json()
                logger.info(f"Получены данные о присутствии в канале {channel}")
                return presence_data
            else:
                logger.error(f"Ошибка получения данных о присутствии: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса данных о присутствии: {str(e)}")
        return None


async def cleanup_test_data(auth_token: str) -> bool:
    """Очистка тестовых данных"""
    success = True
    
    # Удаление тестовых сообщений
    for message_id in test_data.get("test_messages", []):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{API_URL}/messages/{message_id}",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
                
                if response.status_code != 200 and response.status_code != 204:
                    logger.warning(f"Не удалось удалить тестовое сообщение {message_id}: {response.status_code}")
                    success = False
        except Exception as e:
            logger.warning(f"Ошибка при удалении тестового сообщения {message_id}: {str(e)}")
            success = False
    
    logger.info("Очистка тестовых данных завершена")
    return success


async def run_integration_test(verbose: bool = False, cleanup: bool = True) -> bool:
    """Запуск интеграционного теста"""
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info("Запуск интеграционного теста Centrifugo")
    
    # Шаг 1: Получение токена авторизации
    auth_token = await get_auth_token()
    if not auth_token:
        logger.error("Не удалось получить токен авторизации")
        return False
    
    test_data["auth_token"] = auth_token
    
    # Шаг 2: Получение токена Centrifugo
    centrifugo_token = await get_centrifugo_token(auth_token)
    if not centrifugo_token:
        logger.error("Не удалось получить токен Centrifugo")
        return False
    
    test_data["centrifugo_token"] = centrifugo_token
    
    # Шаг 3: Получение списка чатов
    chats = await get_user_chats(auth_token)
    if not chats:
        logger.error("Не удалось получить список чатов")
        return False
    
    if not chats:
        logger.error("У пользователя нет доступных чатов")
        return False
    
    # Берем первый чат для тестирования
    test_chat_id = chats[0]["id"]
    test_data["test_chat_id"] = test_chat_id
    logger.info(f"Выбран чат для тестирования: {test_chat_id}")
    
    # Шаг 4: Отправка тестового сообщения
    channel = f"chat:{test_chat_id}"
    test_message = f"Тестовое сообщение интеграции {datetime.now().isoformat()}"
    
    message_result = await send_message(auth_token, channel, test_message)
    if not message_result:
        logger.error("Не удалось отправить тестовое сообщение")
        return False
    
    message_id = message_result.get("message_id")
    if message_id:
        test_data["test_messages"].append(message_id)
        logger.info(f"Сообщение сохранено с ID: {message_id}")
    
    # Шаг 5: Проверка истории сообщений
    await asyncio.sleep(1)  # Ждем, чтобы сообщение точно сохранилось
    
    messages = await check_message_history(auth_token, test_chat_id)
    if not messages:
        logger.error("Не удалось получить историю сообщений")
        return False
    
    # Проверяем, что наше сообщение есть в истории
    found_message = False
    for msg in messages:
        if msg.get("text") == test_message:
            found_message = True
            break
    
    if not found_message:
        logger.error("Тестовое сообщение не найдено в истории")
        return False
    
    logger.info("Тестовое сообщение успешно найдено в истории")
    
    # Шаг 6: Проверка присутствия
    presence_data = await check_presence(auth_token, channel)
    if not presence_data:
        logger.warning("Не удалось получить данные о присутствии (это может быть нормально, если клиент не подключен)")
    else:
        logger.info(f"Данные о присутствии получены: {json.dumps(presence_data, indent=2)}")
    
    # Очистка тестовых данных
    if cleanup:
        await cleanup_test_data(auth_token)
    
    logger.info("Интеграционный тест успешно завершен")
    return True


def main():
    """Основная функция скрипта"""
    parser = argparse.ArgumentParser(description="Тест интеграции с Centrifugo")
    parser.add_argument("--verbose", action="store_true", help="Включить подробное логирование")
    parser.add_argument("--no-cleanup", action="store_true", help="Не удалять тестовые данные")
    args = parser.parse_args()
    
    try:
        success = asyncio.run(run_integration_test(
            verbose=args.verbose,
            cleanup=not args.no_cleanup
        ))
        
        if success:
            logger.info("Тест интеграции с Centrifugo успешно пройден")
            sys.exit(0)
        else:
            logger.error("Тест интеграции с Centrifugo не пройден")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Тест прерван пользователем")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main() 