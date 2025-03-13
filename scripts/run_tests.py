#!/usr/bin/env python3
"""
Скрипт для удобного запуска тестов проекта WinDI Messenger
"""
import os
import sys
import subprocess
import argparse
import time
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("run_tests")

# Директория проекта
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def run_tests(test_type, verbose=False, coverage=False, full_load=False, fail_fast=False):
    """
    Запускает тесты определенного типа
    
    Args:
        test_type (str): Тип тестов для запуска ('unit', 'integration', 'e2e', 'performance', 'all')
          или путь к конкретному тесту
        verbose (bool): Подробный вывод выполнения тестов
        coverage (bool): Генерировать отчет о покрытии кода
        full_load (bool): Запустить полную версию нагрузочных тестов
        fail_fast (bool): Остановить выполнение при первом падении теста
        
    Returns:
        int: Код возврата процесса pytest
    """
    os.chdir(PROJECT_DIR)
    
    # Формируем команду запуска pytest
    cmd = ["pytest"]
    
    # Добавляем специфичные для типа тестов параметры
    if test_type == "unit":
        cmd.append("tests/unit/")
        cmd.append("-m")
        cmd.append("unit")
    elif test_type == "integration":
        cmd.append("tests/integration/")
        cmd.append("-m")
        cmd.append("integration")
    elif test_type == "e2e":
        cmd.append("tests/e2e/")
        cmd.append("-m")
        cmd.append("e2e")
    elif test_type == "performance":
        cmd.append("tests/performance/")
        cmd.append("-m")
        cmd.append("performance")
    elif test_type == "all":
        # Запуск всех тестов
        pass
    else:
        # Проверяем существование указанного пути
        if os.path.exists(test_type):
            # Запуск конкретного теста или директории
            cmd.append(test_type)
        else:
            logger.error(f"Указанный путь к тесту не существует: {test_type}")
            return 1
    
    # Флаги pytest
    if verbose:
        cmd.append("-v")
    
    if fail_fast:
        cmd.append("-x")
    
    # Покрытие кода
    if coverage:
        cmd.append("--cov=app")
        cmd.append("--cov-report=term")
        cmd.append("--cov-report=html")
    
    # Для нагрузочных тестов
    env = os.environ.copy()
    if full_load and ("performance" in test_type or test_type == "all"):
        env["FULL_LOAD_TEST"] = "1"
    
    # Запуск команды
    logger.info(f"Запуск команды: {' '.join(cmd)}")
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, env=env)
        exit_code = result.returncode
    except KeyboardInterrupt:
        logger.info("Тестирование прервано пользователем")
        exit_code = 130  # Стандартный код для прерывания пользователем
    except Exception as e:
        logger.error(f"Ошибка при запуске тестов: {e}")
        exit_code = 1
    
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"Тесты выполнены за {duration:.2f} секунд")
    
    if coverage:
        logger.info("Отчет о покрытии кода доступен в директории htmlcov/")
    
    return exit_code


def setup_env_file():
    """
    Проверяет наличие .env файла и создает его при необходимости
    
    Returns:
        bool: True, если файл создан или уже существует, False в случае ошибки
    """
    env_path = os.path.join(PROJECT_DIR, ".env")
    if not os.path.exists(env_path):
        logger.info("Файл .env не найден. Создаем тестовый .env файл...")
        
        try:
            with open(env_path, "w") as f:
                f.write("# Тестовые настройки окружения\n")
                f.write("API_URL=http://localhost:8000\n")
                f.write("CENTRIFUGO_URL=http://localhost:8001\n")
                f.write("CENTRIFUGO_WS_URL=ws://localhost:8001/connection/websocket\n")
                f.write("TEST_USER_EMAIL=admin@example.com\n")
                f.write("TEST_USER_PASSWORD=password123\n")
                f.write("TEST_USER2_EMAIL=user1@example.com\n")
                f.write("TEST_USER2_PASSWORD=password123\n")
                f.write("CENTRIFUGO_API_KEY=default-api-key\n")
                f.write("CENTRIFUGO_TOKEN_HMAC_SECRET=secret-key-for-tests\n")
            
            logger.info("Файл .env создан с тестовыми настройками.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при создании файла .env: {e}")
            return False
    else:
        logger.debug("Файл .env уже существует")
        return True


def setup_test_environment():
    """
    Подготовка среды для тестирования
    
    Returns:
        bool: True, если подготовка успешна, False в случае ошибки
    """
    try:
        # Проверяем/создаем файл .env
        if not setup_env_file():
            return False
        
        # Проверяем наличие директории tests
        tests_dir = os.path.join(PROJECT_DIR, "tests")
        if not os.path.exists(tests_dir):
            logger.error(f"Директория тестов не найдена: {tests_dir}")
            return False
        
        # Дополнительные проверки могут быть добавлены здесь
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при подготовке среды тестирования: {e}")
        return False


def main():
    """Основная функция скрипта"""
    parser = argparse.ArgumentParser(description="Запуск тестов WinDI Messenger")
    
    # Обязательный аргумент - тип теста
    parser.add_argument("type", 
                      help="Тип тестов для запуска: unit, integration, e2e, performance, all или путь к конкретному тесту")
    
    # Опциональные аргументы
    parser.add_argument("-v", "--verbose", action="store_true", 
                      help="Подробный вывод выполнения тестов")
    parser.add_argument("-c", "--coverage", action="store_true", 
                      help="Генерировать отчет о покрытии кода")
    parser.add_argument("-f", "--full-load", action="store_true", 
                      help="Запустить полную версию нагрузочных тестов")
    parser.add_argument("-x", "--fail-fast", action="store_true", 
                      help="Остановить выполнение при первом падении теста")
    parser.add_argument("--setup", action="store_true", 
                      help="Подготовить среду для тестирования")
    
    args = parser.parse_args()
    
    # Если нужна подготовка среды
    if args.setup:
        logger.info("Подготовка среды для тестирования...")
        if not setup_test_environment():
            logger.error("Не удалось подготовить среду для тестирования")
            sys.exit(1)
    
    # Проверяем файл .env в любом случае
    setup_env_file()
    
    # Запускаем тесты
    exit_code = run_tests(
        args.type,
        verbose=args.verbose,
        coverage=args.coverage,
        full_load=args.full_load,
        fail_fast=args.fail_fast
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main() 