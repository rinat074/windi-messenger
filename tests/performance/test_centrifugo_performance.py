"""
Тесты производительности для Centrifugo

Эти тесты предназначены для оценки производительности и пропускной способности системы
при работе с Centrifugo и базой данных.

Для запуска с полной нагрузкой используйте:
FULL_LOAD_TEST=1 PERF_CONCURRENT_USERS=20 PERF_MESSAGES_PER_USER=10 pytest tests/performance/test_centrifugo_performance.py -v

Переменные окружения:
- FULL_LOAD_TEST: Установите 1 для запуска полного теста (по умолчанию: 0)
- PERF_CONCURRENT_USERS: Количество одновременных пользователей (по умолчанию: 10)
- PERF_MESSAGES_PER_USER: Сообщений на пользователя (по умолчанию: 5)
- PERF_REPORT_DIR: Директория для сохранения отчетов (по умолчанию: текущая директория)
"""
import pytest
import asyncio
import time
import json
import os
import warnings
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import statistics

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.core.centrifugo import centrifugo_client
from app.db.crud.message import save_message_to_db


# Настройки для тестов производительности
CONCURRENT_USERS = int(os.environ.get("PERF_CONCURRENT_USERS", "10"))
MESSAGES_PER_USER = int(os.environ.get("PERF_MESSAGES_PER_USER", "5"))
FULL_LOAD_TEST = os.environ.get("FULL_LOAD_TEST", "0") == "1"
PERF_REPORT_DIR = os.environ.get("PERF_REPORT_DIR", ".")


@pytest.mark.performance
@pytest.mark.asyncio
async def test_centrifugo_publish_performance():
    """
    Тест производительности публикации сообщений в Centrifugo
    
    Измеряет скорость публикации большого количества сообщений одновременно
    с разных виртуальных пользователей и собирает детальную статистику.
    
    Результаты:
    - Количество успешных и неудачных запросов
    - Общее время выполнения
    - Запросов в секунду
    - Среднее время запроса
    - Процентили P50, P90, P95, P99 времени запросов
    """
    # Пропускаем детальный тест, если не задан флаг FULL_LOAD_TEST
    if not FULL_LOAD_TEST:
        pytest.skip("Пропускаем полный тест производительности. Установите FULL_LOAD_TEST=1 для запуска.")
    
    chat_id = "test-chat-id"
    channel = f"chat:{chat_id}"
    user_id = "test-user-id"
    
    # Статистика
    request_times = []
    error_counts = {
        "network": 0,
        "timeout": 0,
        "auth": 0,
        "server": 0,
        "other": 0
    }
    
    # Функция для отправки сообщения и измерения времени
    async def send_message(message_num):
        start_time = time.time()
        
        try:
            result = await centrifugo_client.publish(
                channel=channel,
                data={
                    "text": f"Тестовое сообщение #{message_num}",
                    "sender_id": user_id,
                    "sender_name": "Test User",
                    "client_message_id": f"perf-test-{message_num}"
                }
            )
            
            end_time = time.time()
            request_time = end_time - start_time
            request_times.append(request_time)
            
            return True
        except httpx.ConnectError as e:
            error_counts["network"] += 1
            print(f"Ошибка сети при отправке сообщения {message_num}: {str(e)}")
            return False
        except httpx.TimeoutException as e:
            error_counts["timeout"] += 1
            print(f"Таймаут при отправке сообщения {message_num}: {str(e)}")
            return False
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                error_counts["auth"] += 1
                print(f"Ошибка авторизации при отправке сообщения {message_num}: {str(e)}")
            elif e.response.status_code >= 500:
                error_counts["server"] += 1
                print(f"Серверная ошибка при отправке сообщения {message_num}: {str(e)}")
            else:
                error_counts["other"] += 1
                print(f"HTTP ошибка при отправке сообщения {message_num}: {str(e)}")
            return False
        except Exception as e:
            error_counts["other"] += 1
            print(f"Непредвиденная ошибка при отправке сообщения {message_num}: {str(e)}")
            return False
    
    # Отправляем сообщения конкурентно
    total_messages = CONCURRENT_USERS * MESSAGES_PER_USER
    print(f"\nОтправка {total_messages} сообщений с {CONCURRENT_USERS} пользователями...")
    
    # Создаем задачи для отправки
    tasks = []
    for i in range(total_messages):
        tasks.append(send_message(i))
    
    # Выполняем все задачи с индикатором прогресса
    progress_interval = max(1, total_messages // 10)
    start_total = time.time()
    
    # Используем as_completed для отслеживания прогресса
    pending = set(asyncio.create_task(t) for t in tasks)
    completed = 0
    
    while pending:
        done, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED, timeout=0.5
        )
        completed += len(done)
        if completed % progress_interval == 0 or completed == total_messages:
            print(f"Прогресс: {completed}/{total_messages} сообщений ({completed * 100 // total_messages}%)")
    
    # Собираем результаты
    results = [task.result() for task in asyncio.all_tasks() 
              if task.get_name().startswith('Task-') and task.done()]
    end_total = time.time()
    
    # Анализируем результаты
    successful = results.count(True)
    failed = results.count(False)
    total_time = end_total - start_total
    requests_per_second = successful / total_time if total_time > 0 else 0
    
    # Статистика времени запросов
    if request_times:
        avg_request_time = statistics.mean(request_times)
        p50_request_time = statistics.median(request_times)
        p90_request_time = sorted(request_times)[int(len(request_times) * 0.9)]
        p95_request_time = sorted(request_times)[int(len(request_times) * 0.95)]
        p99_request_time = sorted(request_times)[int(len(request_times) * 0.99)]
    else:
        avg_request_time = p50_request_time = p90_request_time = p95_request_time = p99_request_time = 0
    
    # Сохраняем результаты
    results = {
        "test_name": "centrifugo_publish_performance",
        "timestamp": datetime.now().isoformat(),
        "parameters": {
            "concurrent_users": CONCURRENT_USERS,
            "messages_per_user": MESSAGES_PER_USER
        },
        "requests": total_messages,
        "successful": successful,
        "failed": failed,
        "error_counts": error_counts,
        "total_time": total_time,
        "requests_per_second": requests_per_second,
        "avg_request_time": avg_request_time,
        "p50_request_time": p50_request_time,
        "p90_request_time": p90_request_time,
        "p95_request_time": p95_request_time,
        "p99_request_time": p99_request_time
    }
    
    # Создаем директорию для отчетов, если её нет
    os.makedirs(PERF_REPORT_DIR, exist_ok=True)
    
    # Записываем результаты в файл
    report_path = os.path.join(PERF_REPORT_DIR, f"load_test_publish_c{CONCURRENT_USERS}.json")
    with open(report_path, "w") as f:
        json.dump({"summary": results, "raw_data": request_times}, f, indent=2)
    
    print(f"\nРезультаты публикации сообщений:")
    print(f"Всего запросов: {total_messages}")
    print(f"Успешных: {successful}, Ошибок: {failed}")
    print(f"Типы ошибок: {error_counts}")
    print(f"Общее время: {total_time:.2f} сек")
    print(f"Запросов в секунду: {requests_per_second:.2f}")
    print(f"Среднее время запроса: {avg_request_time:.4f} сек")
    print(f"P50 время запроса: {p50_request_time:.4f} сек")
    print(f"P90 время запроса: {p90_request_time:.4f} сек")
    print(f"P95 время запроса: {p95_request_time:.4f} сек")
    print(f"P99 время запроса: {p99_request_time:.4f} сек")
    print(f"Отчет сохранен в: {report_path}")
    
    # Базовая проверка производительности
    assert successful > 0
    assert requests_per_second > 1.0, "Производительность ниже ожидаемой"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_message_save_performance(db_session):
    """
    Тест производительности сохранения сообщений в базу данных
    
    Измеряет скорость сохранения большого количества сообщений в БД
    и собирает детальную статистику производительности.
    
    Результаты:
    - Количество успешных и неудачных сохранений
    - Общее время выполнения
    - Операций в секунду
    - Среднее время операции
    - Процентили P50, P90, P95 времени операций
    - Типы и количество ошибок
    """
    # Пропускаем детальный тест, если не задан флаг FULL_LOAD_TEST
    if not FULL_LOAD_TEST:
        pytest.skip("Пропускаем полный тест производительности. Установите FULL_LOAD_TEST=1 для запуска.")
    
    chat_id = "test-chat-id"
    user_id = "test-user-id"
    
    # Статистика
    request_times = []
    error_counts = {
        "db_connection": 0,
        "db_constraint": 0,
        "db_other": 0,
        "other": 0
    }
    
    # Функция для сохранения сообщения и измерения времени
    async def save_message(message_num):
        start_time = time.time()
        
        try:
            # Создаем уникальный client_message_id для каждого сообщения
            client_message_id = f"perf-test-{int(time.time())}-{message_num}"
            
            result = await save_message_to_db(
                db=db_session,
                chat_id=chat_id,
                sender_id=user_id,
                text=f"Тестовое сообщение #{message_num}",
                client_message_id=client_message_id
            )
            
            end_time = time.time()
            request_time = end_time - start_time
            request_times.append(request_time)
            
            return result is not None
        except SQLAlchemyError as e:
            if "ConnectionError" in str(e) or "Connection" in str(e):
                error_counts["db_connection"] += 1
                print(f"Ошибка соединения с БД при сохранении сообщения {message_num}: {str(e)}")
            elif "UniqueViolation" in str(e) or "Constraint" in str(e):
                error_counts["db_constraint"] += 1
                print(f"Ошибка ограничения БД при сохранении сообщения {message_num}: {str(e)}")
            else:
                error_counts["db_other"] += 1
                print(f"Ошибка БД при сохранении сообщения {message_num}: {str(e)}")
            return False
        except Exception as e:
            error_counts["other"] += 1
            print(f"Непредвиденная ошибка при сохранении сообщения {message_num}: {str(e)}")
            return False
    
    # Сохраняем сообщения последовательно
    total_messages = MESSAGES_PER_USER  # Меньше сообщений для БД-теста
    print(f"\nСохранение {total_messages} сообщений в базу данных...")
    
    # Создаем задачи для сохранения
    tasks = []
    for i in range(total_messages):
        tasks.append(save_message(i))
    
    # Выполняем все задачи с индикатором прогресса
    progress_interval = max(1, total_messages // 5)
    start_total = time.time()
    
    # Используем as_completed для отслеживания прогресса
    pending = set(asyncio.create_task(t) for t in tasks)
    completed = 0
    
    while pending:
        done, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED, timeout=0.5
        )
        completed += len(done)
        if completed % progress_interval == 0 or completed == total_messages:
            print(f"Прогресс: {completed}/{total_messages} сообщений ({completed * 100 // total_messages}%)")
    
    # Собираем результаты
    results = [task.result() for task in asyncio.all_tasks() 
              if task.get_name().startswith('Task-') and task.done()]
    end_total = time.time()
    
    # Анализируем результаты
    successful = results.count(True)
    failed = results.count(False)
    total_time = end_total - start_total
    operations_per_second = successful / total_time if total_time > 0 else 0
    
    # Статистика времени операций
    if request_times:
        avg_request_time = statistics.mean(request_times)
        p50_request_time = statistics.median(request_times)
        p90_request_time = sorted(request_times)[int(len(request_times) * 0.9)]
        p95_request_time = sorted(request_times)[int(len(request_times) * 0.95)]
    else:
        avg_request_time = p50_request_time = p90_request_time = p95_request_time = 0
    
    # Сохраняем результаты
    results = {
        "test_name": "message_save_performance",
        "timestamp": datetime.now().isoformat(),
        "parameters": {
            "messages": total_messages
        },
        "operations": total_messages,
        "successful": successful,
        "failed": failed,
        "error_counts": error_counts,
        "total_time": total_time,
        "operations_per_second": operations_per_second,
        "avg_operation_time": avg_request_time,
        "p50_operation_time": p50_request_time,
        "p90_operation_time": p90_request_time,
        "p95_operation_time": p95_request_time
    }
    
    # Создаем директорию для отчетов, если её нет
    os.makedirs(PERF_REPORT_DIR, exist_ok=True)
    
    # Записываем результаты в файл
    report_path = os.path.join(PERF_REPORT_DIR, "load_test_db_save.json")
    with open(report_path, "w") as f:
        json.dump({"summary": results, "raw_data": request_times}, f, indent=2)
    
    print(f"\nРезультаты сохранения сообщений:")
    print(f"Всего операций: {total_messages}")
    print(f"Успешных: {successful}, Ошибок: {failed}")
    print(f"Типы ошибок: {error_counts}")
    print(f"Общее время: {total_time:.2f} сек")
    print(f"Операций в секунду: {operations_per_second:.2f}")
    print(f"Среднее время операции: {avg_request_time:.4f} сек")
    print(f"P50 время операции: {p50_request_time:.4f} сек")
    print(f"P90 время операции: {p90_request_time:.4f} сек")
    print(f"P95 время операции: {p95_request_time:.4f} сек")
    print(f"Отчет сохранен в: {report_path}")
    
    # Базовая проверка производительности
    assert successful > 0
    assert operations_per_second > 1.0, "Производительность БД ниже ожидаемой" 