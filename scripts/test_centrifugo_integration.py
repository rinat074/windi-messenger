#!/usr/bin/env python3
"""
Скрипт для тестирования интеграции Centrifugo с WinDI Messenger.

Этот скрипт выполняет полную проверку:
1. Подключение к Centrifugo
2. Аутентификация пользователя
3. Получение токена Centrifugo
4. Подписка на каналы
5. Отправка и получение сообщений
6. Проверка присутствия пользователей
7. Контроль доступа к каналам

Использование:
    python scripts/test_centrifugo_integration.py
"""

import os
import sys
import json
import time
import asyncio
import logging
import argparse
import datetime
from typing import Dict, Any, List, Optional
from uuid import uuid4

import httpx
from dotenv import load_dotenv
import websockets

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("centrifugo-test")

# Загрузка переменных окружения
load_dotenv()

# Константы
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
CENTRIFUGO_WS_URL = os.getenv("CENTRIFUGO_WS_URL", "ws://localhost:8001/connection/websocket")
CENTRIFUGO_HTTP_URL = os.getenv("CENTRIFUGO_HTTP_URL", "http://localhost:8001")
API_KEY = os.getenv("CENTRIFUGO_API_KEY", "change-this-to-a-long-random-string-in-production")

# Тестовые пользователи
TEST_USERS = [
    {"email": "user1@example.com", "password": "Password123!"},
    {"email": "user2@example.com", "password": "Password123!"}
]


class CentrifugoClient:
    """Клиент для взаимодействия с Centrifugo"""
    
    def __init__(self, ws_url: str, token: str = None):
        self.ws_url = ws_url
        self.token = token
        self.connection = None
        self.client_id = None
        self.subscriptions = {}
        self.message_handlers = {}
        self.join_handlers = {}
        self.leave_handlers = {}
        self.message_queue = asyncio.Queue()
        self.running = False
    
    async def connect(self) -> bool:
        """Подключение к Centrifugo"""
        try:
            # Формируем URL с токеном если он задан
            url = self.ws_url
            if self.token:
                url = f"{self.ws_url}?token={self.token}"
            
            logger.info(f"Подключение к Centrifugo: {url}")
            self.connection = await websockets.connect(url)
            
            # Отправляем команду connect
            connect_message = {
                "id": str(uuid4()),
                "method": "connect",
                "params": {}
            }
            await self.connection.send(json.dumps(connect_message))
            
            # Получаем ответ
            response = await self.connection.recv()
            data = json.loads(response)
            
            if "error" in data:
                logger.error(f"Ошибка при подключении: {data['error']}")
                return False
            
            # Сохраняем client_id
            self.client_id = data.get("result", {}).get("client", "")
            logger.info(f"Подключено к Centrifugo с client_id: {self.client_id}")
            
            # Запускаем фоновое чтение сообщений
            self.running = True
            asyncio.create_task(self._read_messages())
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при подключении к Centrifugo: {str(e)}")
            return False
    
    async def disconnect(self):
        """Отключение от Centrifugo"""
        self.running = False
        if self.connection:
            await self.connection.close()
            self.connection = None
            self.client_id = None
            logger.info("Отключено от Centrifugo")
    
    async def subscribe(self, channel: str) -> bool:
        """Подписка на канал"""
        if not self.connection:
            logger.error("Нет активного подключения к Centrifugo")
            return False
        
        try:
            # Отправляем команду subscribe
            subscribe_message = {
                "id": str(uuid4()),
                "method": "subscribe",
                "params": {
                    "channel": channel
                }
            }
            await self.connection.send(json.dumps(subscribe_message))
            
            # Ответ будет обработан в _read_messages
            self.subscriptions[channel] = {
                "status": "subscribing",
                "last_message": None
            }
            
            logger.info(f"Отправлен запрос на подписку на канал: {channel}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при подписке на канал {channel}: {str(e)}")
            return False
    
    async def unsubscribe(self, channel: str) -> bool:
        """Отписка от канала"""
        if not self.connection:
            logger.error("Нет активного подключения к Centrifugo")
            return False
        
        try:
            # Отправляем команду unsubscribe
            unsubscribe_message = {
                "id": str(uuid4()),
                "method": "unsubscribe",
                "params": {
                    "channel": channel
                }
            }
            await self.connection.send(json.dumps(unsubscribe_message))
            
            # Удаляем канал из списка подписок
            if channel in self.subscriptions:
                del self.subscriptions[channel]
            
            logger.info(f"Отписка от канала: {channel}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отписке от канала {channel}: {str(e)}")
            return False
    
    async def publish(self, channel: str, data: Dict[str, Any]) -> bool:
        """Публикация сообщения через WebSocket API"""
        if not self.connection:
            logger.error("Нет активного подключения к Centrifugo")
            return False
        
        try:
            # Отправляем команду publish
            publish_message = {
                "id": str(uuid4()),
                "method": "publish",
                "params": {
                    "channel": channel,
                    "data": data
                }
            }
            await self.connection.send(json.dumps(publish_message))
            
            logger.info(f"Отправлено сообщение в канал {channel}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при публикации в канал {channel}: {str(e)}")
            return False
    
    async def presence(self, channel: str) -> Dict[str, Any]:
        """Получение списка пользователей в канале"""
        if not self.connection:
            logger.error("Нет активного подключения к Centrifugo")
            return {}
        
        try:
            # Отправляем команду presence
            message_id = str(uuid4())
            presence_message = {
                "id": message_id,
                "method": "presence",
                "params": {
                    "channel": channel
                }
            }
            await self.connection.send(json.dumps(presence_message))
            
            # Ждем ответ с нужным id
            start_time = time.time()
            while time.time() - start_time < 5:  # Ждем ответ максимум 5 секунд
                try:
                    message = await asyncio.wait_for(self.message_queue.get(), 1.0)
                    if message.get("id") == message_id:
                        logger.info(f"Получен ответ presence для канала {channel}")
                        return message.get("result", {})
                except asyncio.TimeoutError:
                    continue
            
            logger.error(f"Не получен ответ presence для канала {channel} в течение 5 секунд")
            return {}
        except Exception as e:
            logger.error(f"Ошибка при получении presence для канала {channel}: {str(e)}")
            return {}
    
    async def history(self, channel: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Получение истории сообщений канала"""
        if not self.connection:
            logger.error("Нет активного подключения к Centrifugo")
            return []
        
        try:
            # Отправляем команду history
            message_id = str(uuid4())
            history_message = {
                "id": message_id,
                "method": "history",
                "params": {
                    "channel": channel,
                    "limit": limit
                }
            }
            await self.connection.send(json.dumps(history_message))
            
            # Ждем ответ с нужным id
            start_time = time.time()
            while time.time() - start_time < 5:  # Ждем ответ максимум 5 секунд
                try:
                    message = await asyncio.wait_for(self.message_queue.get(), 1.0)
                    if message.get("id") == message_id:
                        logger.info(f"Получен ответ history для канала {channel}")
                        return message.get("result", {}).get("publications", [])
                except asyncio.TimeoutError:
                    continue
            
            logger.error(f"Не получен ответ history для канала {channel} в течение 5 секунд")
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении history для канала {channel}: {str(e)}")
            return []
    
    def add_message_handler(self, channel: str, handler):
        """Добавление обработчика сообщений для канала"""
        self.message_handlers[channel] = handler
    
    def add_join_handler(self, channel: str, handler):
        """Добавление обработчика входа для канала"""
        self.join_handlers[channel] = handler
    
    def add_leave_handler(self, channel: str, handler):
        """Добавление обработчика выхода для канала"""
        self.leave_handlers[channel] = handler
    
    async def _read_messages(self):
        """Фоновая задача для чтения сообщений"""
        if not self.connection:
            return
        
        try:
            while self.running and self.connection:
                message = await self.connection.recv()
                data = json.loads(message)
                
                # Обработка разных типов сообщений
                if "result" in data:
                    # Ответ на команду
                    if "subscribe" in data.get("result", {}):
                        channel = data.get("result", {}).get("subscribe", {}).get("channel")
                        if channel:
                            logger.info(f"Успешная подписка на канал: {channel}")
                            if channel in self.subscriptions:
                                self.subscriptions[channel]["status"] = "subscribed"
                    
                    # Добавляем сообщение в очередь для других методов
                    await self.message_queue.put(data)
                
                elif "push" in data:
                    # Push-сообщение от сервера
                    push_data = data.get("push", {})
                    channel = push_data.get("channel")
                    
                    # Обрабатываем публикации
                    if "pub" in push_data:
                        publication = push_data.get("pub")
                        logger.info(f"Получена публикация в канале {channel}: {publication}")
                        
                        # Вызываем обработчик если он есть
                        if channel in self.message_handlers:
                            self.message_handlers[channel](publication)
                        
                        # Сохраняем последнее сообщение
                        if channel in self.subscriptions:
                            self.subscriptions[channel]["last_message"] = publication
                    
                    # Обрабатываем события входа
                    if "join" in push_data:
                        join_info = push_data.get("join")
                        logger.info(f"Пользователь присоединился к каналу {channel}: {join_info}")
                        
                        # Вызываем обработчик если он есть
                        if channel in self.join_handlers:
                            self.join_handlers[channel](join_info)
                    
                    # Обрабатываем события выхода
                    if "leave" in push_data:
                        leave_info = push_data.get("leave")
                        logger.info(f"Пользователь покинул канал {channel}: {leave_info}")
                        
                        # Вызываем обработчик если он есть
                        if channel in self.leave_handlers:
                            self.leave_handlers[channel](leave_info)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Соединение с Centrifugo закрыто")
        except Exception as e:
            logger.error(f"Ошибка при чтении сообщений: {str(e)}")
        finally:
            self.running = False


async def get_auth_token(email: str, password: str) -> Optional[str]:
    """Аутентификация пользователя и получение токена доступа"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/users/login",
                json={"email": email, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Успешная аутентификация пользователя {email}")
                return data.get("access_token")
            else:
                logger.error(f"Ошибка аутентификации: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса аутентификации: {str(e)}")
        return None


async def get_centrifugo_token(auth_token: str) -> Optional[str]:
    """Получение токена для подключения к Centrifugo"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/centrifugo/token",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("token")
                logger.info("Успешно получен токен Centrifugo")
                return token
            else:
                logger.error(f"Ошибка при получении токена Centrifugo: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса токена Centrifugo: {str(e)}")
        return None


async def get_user_chats(auth_token: str) -> List[Dict[str, Any]]:
    """Получение списка чатов пользователя"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_URL}/chats",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                chats = data.get("items", [])
                logger.info(f"Получено {len(chats)} чатов")
                return chats
            else:
                logger.error(f"Ошибка при получении списка чатов: {response.status_code} - {response.text}")
                return []
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса списка чатов: {str(e)}")
        return []


async def create_chat(auth_token: str, name: str, is_private: bool = False) -> Optional[Dict[str, Any]]:
    """Создание нового чата"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/chats",
                json={"name": name, "is_private": is_private},
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            if response.status_code in (200, 201):
                chat = response.json()
                logger.info(f"Создан чат: {chat.get('name')} (ID: {chat.get('id')})")
                return chat
            else:
                logger.error(f"Ошибка при создании чата: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса создания чата: {str(e)}")
        return None


async def send_message(auth_token: str, chat_id: int, text: str) -> Optional[Dict[str, Any]]:
    """Отправка сообщения через API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/centrifugo/publish?chat_id={chat_id}",
                json={"content": text, "attachments": []},
                headers={
                    "Authorization": f"Bearer {auth_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                message = response.json()
                logger.info(f"Отправлено сообщение в чат {chat_id}: {text}")
                return message
            else:
                logger.error(f"Ошибка при отправке сообщения: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса отправки сообщения: {str(e)}")
        return None


async def get_presence(auth_token: str, chat_id: int) -> Dict[str, Any]:
    """Получение списка присутствующих пользователей через API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_URL}/centrifugo/presence/{chat_id}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Получены данные о присутствии в чате {chat_id}")
                return data
            else:
                logger.error(f"Ошибка при получении данных о присутствии: {response.status_code} - {response.text}")
                return {}
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса данных о присутствии: {str(e)}")
        return {}


async def test_simultaneous_connections():
    """Тестирование одновременных подключений пользователей"""
    logger.info("=== Тестирование одновременных подключений ===")
    
    # Авторизуем двух пользователей
    auth_tokens = []
    centrifugo_tokens = []
    
    for user in TEST_USERS:
        auth_token = await get_auth_token(user["email"], user["password"])
        if not auth_token:
            logger.error(f"Не удалось авторизовать пользователя {user['email']}")
            continue
        
        centrifugo_token = await get_centrifugo_token(auth_token)
        if not centrifugo_token:
            logger.error(f"Не удалось получить токен Centrifugo для пользователя {user['email']}")
            continue
        
        auth_tokens.append(auth_token)
        centrifugo_tokens.append(centrifugo_token)
    
    if len(auth_tokens) < 2:
        logger.error("Недостаточно авторизованных пользователей для теста")
        return False
    
    # Подключаемся к Centrifugo с двумя клиентами
    client1 = CentrifugoClient(CENTRIFUGO_WS_URL, centrifugo_tokens[0])
    client2 = CentrifugoClient(CENTRIFUGO_WS_URL, centrifugo_tokens[1])
    
    connected1 = await client1.connect()
    connected2 = await client2.connect()
    
    if not connected1 or not connected2:
        logger.error("Не удалось подключить обоих пользователей")
        return False
    
    logger.info("Оба пользователя успешно подключены к Centrifugo")
    
    try:
        # Создаем тестовый чат для общения
        chat_name = f"Тестовый чат Centrifugo {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        chat = await create_chat(auth_tokens[0], chat_name)
        
        if not chat:
            logger.error("Не удалось создать тестовый чат")
            return False
        
        chat_id = chat["id"]
        
        # Подписываемся на канал чата
        channel = f"chat:{chat_id}"
        
        # Переменные для отслеживания полученных сообщений
        received_messages = set()
        message_event = asyncio.Event()
        
        # Обработчик сообщений для клиента 2
        def message_handler(message):
            received_messages.add(message["data"]["content"])
            message_event.set()
        
        # Подписываемся на канал чата для обоих пользователей
        await client1.subscribe(channel)
        await client2.subscribe(channel)
        
        # Добавляем обработчик сообщений для клиента 2
        client2.add_message_handler(channel, message_handler)
        
        # Ждем немного для завершения подписки
        await asyncio.sleep(1)
        
        # Отправляем тестовое сообщение от первого пользователя
        test_message = f"Тестовое сообщение от пользователя 1: {uuid4()}"
        result = await send_message(auth_tokens[0], chat_id, test_message)
        
        if not result:
            logger.error("Не удалось отправить тестовое сообщение")
            return False
        
        # Ждем получения сообщения вторым пользователем
        try:
            await asyncio.wait_for(message_event.wait(), 5)
        except asyncio.TimeoutError:
            logger.error("Не получено сообщение вторым пользователем в течение 5 секунд")
            return False
        
        # Проверяем, получено ли сообщение
        if test_message in received_messages:
            logger.info("Второй пользователь успешно получил сообщение от первого пользователя")
        else:
            logger.error("Второй пользователь не получил ожидаемое сообщение")
            return False
        
        # Проверяем presence API
        presence_data = await get_presence(auth_tokens[0], chat_id)
        clients = presence_data.get("clients", {})
        
        if len(clients) >= 2:
            logger.info(f"Обнаружено {len(clients)} клиентов в чате через Presence API")
        else:
            logger.warning(f"Обнаружено только {len(clients)} клиентов в чате, ожидалось минимум 2")
        
        # Тест завершен успешно
        logger.info("Тест одновременных подключений завершен успешно")
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении теста одновременных подключений: {str(e)}")
        return False
    
    finally:
        # Отключаемся от Centrifugo
        await client1.disconnect()
        await client2.disconnect()


async def test_access_control():
    """Тестирование контроля доступа к каналам"""
    logger.info("=== Тестирование контроля доступа к каналам ===")
    
    # Авторизуем двух пользователей
    auth_tokens = []
    centrifugo_tokens = []
    
    for user in TEST_USERS:
        auth_token = await get_auth_token(user["email"], user["password"])
        if not auth_token:
            logger.error(f"Не удалось авторизовать пользователя {user['email']}")
            continue
        
        centrifugo_token = await get_centrifugo_token(auth_token)
        if not centrifugo_token:
            logger.error(f"Не удалось получить токен Centrifugo для пользователя {user['email']}")
            continue
        
        auth_tokens.append(auth_token)
        centrifugo_tokens.append(centrifugo_token)
    
    if len(auth_tokens) < 2:
        logger.error("Недостаточно авторизованных пользователей для теста")
        return False
    
    # Подключаемся к Centrifugo для первого пользователя
    client1 = CentrifugoClient(CENTRIFUGO_WS_URL, centrifugo_tokens[0])
    connected1 = await client1.connect()
    
    if not connected1:
        logger.error("Не удалось подключить первого пользователя")
        return False
    
    try:
        # Создаем приватный чат для первого пользователя
        chat_name = f"Приватный тест чат {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        chat = await create_chat(auth_tokens[0], chat_name, is_private=True)
        
        if not chat:
            logger.error("Не удалось создать приватный чат")
            return False
        
        chat_id = chat["id"]
        channel = f"chat:{chat_id}"
        
        # Подписываемся на канал чата для первого пользователя
        subscribed1 = await client1.subscribe(channel)
        
        if not subscribed1:
            logger.error("Не удалось подписаться на канал для первого пользователя")
            return False
        
        # Подписываемся на канал чата для второго пользователя
        client2 = CentrifugoClient(CENTRIFUGO_WS_URL, centrifugo_tokens[1])
        connected2 = await client2.connect()
        
        if not connected2:
            logger.error("Не удалось подключить второго пользователя")
            return False
        
        # Пытаемся подписаться на приватный канал
        subscribed2 = await client2.subscribe(channel)
        
        # Ждем немного для проверки статуса подписки
        await asyncio.sleep(2)
        
        # Проверяем была ли успешной подписка
        if channel in client2.subscriptions and client2.subscriptions[channel]["status"] == "subscribed":
            logger.error("Второй пользователь смог подписаться на приватный канал первого пользователя")
            return False
        else:
            logger.info("Тест контроля доступа пройден успешно - второй пользователь не смог подписаться на приватный канал")
        
        # Тест завершен успешно
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении теста контроля доступа: {str(e)}")
        return False
    
    finally:
        # Отключаемся от Centrifugo
        if client1:
            await client1.disconnect()
        if client2:
            await client2.disconnect()


async def test_message_history():
    """Тестирование истории сообщений"""
    logger.info("=== Тестирование истории сообщений ===")
    
    # Авторизуем пользователя
    auth_token = await get_auth_token(TEST_USERS[0]["email"], TEST_USERS[0]["password"])
    if not auth_token:
        logger.error(f"Не удалось авторизовать пользователя {TEST_USERS[0]['email']}")
        return False
    
    centrifugo_token = await get_centrifugo_token(auth_token)
    if not centrifugo_token:
        logger.error(f"Не удалось получить токен Centrifugo для пользователя {TEST_USERS[0]['email']}")
        return False
    
    # Подключаемся к Centrifugo
    client = CentrifugoClient(CENTRIFUGO_WS_URL, centrifugo_token)
    connected = await client.connect()
    
    if not connected:
        logger.error("Не удалось подключить пользователя")
        return False
    
    try:
        # Получаем список чатов пользователя
        chats = await get_user_chats(auth_token)
        
        if not chats:
            logger.warning("У пользователя нет доступных чатов")
            
            # Создаем тестовый чат
            chat_name = f"Тестовый чат для истории {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            chat = await create_chat(auth_token, chat_name)
            
            if not chat:
                logger.error("Не удалось создать тестовый чат")
                return False
            
            chat_id = chat["id"]
            
            # Отправляем несколько сообщений
            for i in range(5):
                message_text = f"Тестовое сообщение #{i+1} для проверки истории"
                await send_message(auth_token, chat_id, message_text)
                await asyncio.sleep(0.5)  # Небольшая пауза между сообщениями
        
        else:
            # Берем первый доступный чат
            chat_id = chats[0]["id"]
        
        channel = f"chat:{chat_id}"
        
        # Подписываемся на канал чата
        subscribed = await client.subscribe(channel)
        
        if not subscribed:
            logger.error("Не удалось подписаться на канал чата")
            return False
        
        # Получаем историю сообщений
        await asyncio.sleep(1)  # Пауза, чтобы убедиться что подписка завершена
        history = await client.history(channel)
        
        if not history:
            logger.warning("История сообщений пуста")
        else:
            logger.info(f"Получено {len(history)} сообщений из истории чата {chat_id}")
            
            # Выводим последние 3 сообщения
            for i, message in enumerate(history[:3]):
                logger.info(f"Сообщение #{i+1}: {message.get('data', {}).get('content', 'Нет текста')}")
        
        # Тест завершен успешно
        logger.info("Тест истории сообщений завершен")
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении теста истории сообщений: {str(e)}")
        return False
    
    finally:
        # Отключаемся от Centrifugo
        await client.disconnect()


async def main():
    """Основная функция тестирования"""
    logger.info("Начинаем тестирование интеграции Centrifugo...")
    
    tests = [
        ("Одновременных подключений", test_simultaneous_connections),
        ("Контроля доступа", test_access_control),
        ("Истории сообщений", test_message_history)
    ]
    
    results = []
    
    # Выполняем каждый тест
    for name, test_func in tests:
        logger.info(f"\n\n===== Запуск теста: {name} =====\n")
        try:
            start_time = time.time()
            success = await test_func()
            end_time = time.time()
            
            results.append((name, success, end_time - start_time))
        except Exception as e:
            logger.error(f"Исключение при выполнении теста {name}: {str(e)}")
            results.append((name, False, 0))
    
    # Выводим сводку результатов
    logger.info("\n\n===== Результаты тестирования =====")
    
    all_passed = True
    for name, success, duration in results:
        status = "УСПЕХ" if success else "НЕУДАЧА"
        logger.info(f"Тест {name}: {status} ({duration:.2f} с)")
        all_passed = all_passed and success
    
    if all_passed:
        logger.info("\nВсе тесты выполнены успешно! Интеграция Centrifugo работает корректно.")
        return 0
    else:
        logger.error("\nНекоторые тесты не пройдены. Проверьте журнал для получения подробностей.")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Тестирование интеграции Centrifugo")
    args = parser.parse_args()
    
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Тестирование прервано пользователем")
        sys.exit(1) 