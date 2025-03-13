#!/usr/bin/env python3
"""
Скрипт для проверки работоспособности Centrifugo.

Этот скрипт выполняет базовую проверку подключения к Centrifugo,
проверяет доступность API, работу прокси-эндпоинтов и тестирует
публикацию сообщений через API.

Использование:
    python scripts/check_centrifugo.py
"""

import os
import sys
import json
import time
import asyncio
import argparse
import logging
from typing import Optional

import httpx
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("centrifugo-check")

# Загрузка переменных окружения
load_dotenv()

# Константы
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
CENTRIFUGO_URL = os.getenv("CENTRIFUGO_URL", "http://localhost:8001")
CENTRIFUGO_ADMIN_URL = os.getenv("CENTRIFUGO_ADMIN_URL", "http://localhost:8002")
CENTRIFUGO_API_KEY = os.getenv("CENTRIFUGO_API_KEY", "change-this-to-a-long-random-string-in-production")

# Пользовательские данные
TEST_USER = {
    "email": "test@example.com",
    "password": "Password123!"
}


async def check_api_health() -> bool:
    """Проверка работоспособности API сервера"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/health")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"API сервер работает: {data}")
                return True
            else:
                logger.error(f"API сервер недоступен: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Ошибка при проверке API: {str(e)}")
        return False


async def check_centrifugo_health() -> bool:
    """Проверка работоспособности Centrifugo"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{CENTRIFUGO_URL}/health")
            if response.status_code == 200:
                logger.info(f"Centrifugo работает: {response.text}")
                return True
            else:
                logger.error(f"Centrifugo недоступен: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Ошибка при проверке Centrifugo: {str(e)}")
        return False


async def check_centrifugo_api() -> bool:
    """Проверка API Centrifugo с использованием info метода"""
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"apikey {CENTRIFUGO_API_KEY}"
            }
            payload = {
                "method": "info"
            }
            
            response = await client.post(
                f"{CENTRIFUGO_URL}/api",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Centrifugo API работает. Информация: {json.dumps(data, indent=2)}")
                return True
            else:
                logger.error(f"Centrifugo API недоступен: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Ошибка при проверке Centrifugo API: {str(e)}")
        return False


async def login_user() -> Optional[str]:
    """Авторизация пользователя и получение токена"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/users/login",
                json=TEST_USER
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                logger.info(f"Успешный вход пользователя {TEST_USER['email']}")
                return token
            else:
                logger.error(f"Ошибка при входе: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при входе: {str(e)}")
        return None


async def get_centrifugo_token(auth_token: str) -> Optional[str]:
    """Получение токена для подключения к Centrifugo"""
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {auth_token}"
            }
            response = await client.post(
                f"{API_URL}/centrifugo/token",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("token")
                logger.info("Получен токен Centrifugo")
                return token
            else:
                logger.error(f"Ошибка при получении токена Centrifugo: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при получении токена Centrifugo: {str(e)}")
        return None


async def publish_test_message(auth_token: str) -> bool:
    """Публикация тестового сообщения через API"""
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }
            
            # Создаем тестовый чат
            response = await client.post(
                f"{API_URL}/chats",
                json={
                    "name": "Тестовый чат Centrifugo",
                    "is_private": False
                },
                headers=headers
            )
            
            if response.status_code not in (200, 201):
                logger.error(f"Ошибка при создании чата: {response.status_code} - {response.text}")
                return False
            
            chat_data = response.json()
            chat_id = chat_data.get("id")
            
            # Публикуем тестовое сообщение
            channel = f"chat:{chat_id}"
            message_data = {
                "text": "Тестовое сообщение для проверки Centrifugo",
                "type": "message",
                "client_message_id": f"test_{int(time.time())}"
            }
            
            response = await client.post(
                f"{API_URL}/centrifugo/publish",
                params={"channel": channel},
                json=message_data,
                headers=headers
            )
            
            if response.status_code == 200:
                logger.info(f"Сообщение опубликовано в канал {channel}")
                return True
            else:
                logger.error(f"Ошибка при публикации сообщения: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Ошибка при публикации сообщения: {str(e)}")
        return False


async def main():
    """Основная функция проверки"""
    logger.info("Начинаем проверку Centrifugo...")
    
    # Проверка здоровья сервисов
    api_ok = await check_api_health()
    centrifugo_ok = await check_centrifugo_health()
    
    if not api_ok or not centrifugo_ok:
        logger.error("Базовая проверка сервисов не пройдена")
        return 1
    
    # Проверка API Centrifugo
    centrifugo_api_ok = await check_centrifugo_api()
    if not centrifugo_api_ok:
        logger.error("Проверка API Centrifugo не пройдена")
        return 1
    
    # Проверка логина и получения токена
    auth_token = await login_user()
    if not auth_token:
        logger.error("Не удалось авторизоваться. Возможно, пользователь не существует. Создайте тестового пользователя.")
        return 1
    
    # Получение токена Centrifugo
    centrifugo_token = await get_centrifugo_token(auth_token)
    if not centrifugo_token:
        logger.error("Не удалось получить токен Centrifugo")
        return 1
    
    # Публикация тестового сообщения
    message_ok = await publish_test_message(auth_token)
    if not message_ok:
        logger.error("Не удалось опубликовать тестовое сообщение")
        return 1
    
    logger.info("Проверка Centrifugo успешно завершена!")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Проверка работоспособности Centrifugo")
    args = parser.parse_args()
    
    # В Python 3.11+ можно было бы использовать asyncio.run() напрямую
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Проверка прервана пользователем")
        sys.exit(1) 