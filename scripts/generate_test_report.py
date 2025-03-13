#!/usr/bin/env python3
"""
Скрипт для генерации отчетов о тестировании проекта WinDI Messenger

Этот скрипт собирает данные о выполненных тестах из различных источников:
- Результаты запуска pytest
- Отчеты о покрытии кода
- Результаты нагрузочного тестирования

И генерирует отчеты в форматах HTML и JSON.
"""
import os
import json
import argparse
import subprocess
import datetime
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, Tuple

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_report")

# Директория проекта
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Директория для отчетов
REPORTS_DIR = os.path.join(PROJECT_DIR, "reports")

# Шаблон HTML для отчета
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчет о тестировании - WinDI Messenger</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .summary {
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        .summary-box {
            flex: 1;
            min-width: 200px;
            margin: 10px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .success {
            color: #28a745;
        }
        .failure {
            color: #dc3545;
        }
        .warning {
            color: #ffc107;
        }
        .progress-bar {
            height: 20px;
            background-color: #e9ecef;
            border-radius: 5px;
            margin-top: 5px;
            overflow: hidden;
        }
        .progress-value {
            height: 100%;
            background-color: #28a745;
            border-radius: 5px;
        }
        pre {
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }
        .chart-container {
            height: 300px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <h1>Отчет о тестировании - WinDI Messenger</h1>
    <p>Сгенерирован: {generation_time}</p>
    
    <div class="summary">
        <div class="summary-box">
            <h3>Общая статистика</h3>
            <p>Всего тестов: <strong>{total_tests}</strong></p>
            <p>Успешных: <strong class="success">{passed_tests}</strong></p>
            <p>Неуспешных: <strong class="failure">{failed_tests}</strong></p>
            <p>Пропущенных: <strong class="warning">{skipped_tests}</strong></p>
            <div class="progress-bar">
                <div class="progress-value" style="width: {pass_percentage}%"></div>
            </div>
        </div>
        
        <div class="summary-box">
            <h3>Покрытие кода</h3>
            <p>Общее покрытие: <strong>{coverage_percentage}%</strong></p>
            <p>Покрытые строки: <strong>{covered_lines}</strong></p>
            <p>Непокрытые строки: <strong>{missed_lines}</strong></p>
            <div class="progress-bar">
                <div class="progress-value" style="width: {coverage_percentage}%"></div>
            </div>
        </div>
        
        <div class="summary-box">
            <h3>Время выполнения</h3>
            <p>Общее время: <strong>{total_time} сек</strong></p>
            <p>Среднее время теста: <strong>{avg_test_time} сек</strong></p>
            <p>Самый долгий тест: <strong>{slowest_test_time} сек</strong></p>
        </div>
    </div>
    
    <h2>Результаты по типам тестов</h2>
    <table>
        <tr>
            <th>Тип теста</th>
            <th>Всего</th>
            <th>Успешно</th>
            <th>Неуспешно</th>
            <th>Пропущено</th>
            <th>Время (сек)</th>
        </tr>
        {test_types_rows}
    </table>
    
    <h2>Неуспешные тесты</h2>
    {failed_tests_content}
    
    <h2>Медленные тесты (топ 10)</h2>
    <table>
        <tr>
            <th>Тест</th>
            <th>Время (сек)</th>
            <th>Статус</th>
        </tr>
        {slow_tests_rows}
    </table>
    
    <h2>Покрытие кода по модулям</h2>
    <table>
        <tr>
            <th>Модуль</th>
            <th>Покрытие (%)</th>
            <th>Покрытые строки</th>
            <th>Непокрытые строки</th>
        </tr>
        {coverage_rows}
    </table>
    
    <h2>Результаты нагрузочного тестирования</h2>
    {performance_results}
    
    <footer>
        <p><strong>WinDI Messenger</strong> - Отчет о тестировании</p>
    </footer>
</body>
</html>
"""


def ensure_reports_dir() -> str:
    """
    Создает директорию для отчетов, если она не существует
    
    Returns:
        str: Путь к директории для отчетов
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return REPORTS_DIR


def run_pytest_with_reports(test_type: str) -> Tuple[int, str, str]:
    """
    Запускает pytest с генерацией отчетов в формате JUnit XML и Coverage
    
    Args:
        test_type: Тип тестов для запуска ('unit', 'integration', 'e2e', 'performance', 'all')
        
    Returns:
        Tuple[int, str, str]: Код возврата, путь к JUnit XML файлу, путь к Coverage XML файлу
    """
    reports_dir = ensure_reports_dir()
    junit_xml = os.path.join(reports_dir, f"{test_type}_results.xml")
    coverage_xml = os.path.join(reports_dir, f"{test_type}_coverage.xml")
    
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
        # Запуск конкретного теста или директории
        cmd.append(test_type)
    
    # Добавляем флаги для генерации отчетов
    cmd.extend([
        "--junitxml", junit_xml,
        "--cov=app",
        "--cov-report=xml:" + coverage_xml
    ])
    
    logger.info(f"Запуск команды: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, junit_xml, coverage_xml
    except Exception as e:
        logger.error(f"Ошибка при запуске тестов: {e}")
        return 1, junit_xml, coverage_xml


def parse_junit_xml(junit_file: str) -> Dict[str, Any]:
    """
    Парсит JUnit XML файл с результатами тестов
    
    Args:
        junit_file: Путь к JUnit XML файлу
        
    Returns:
        Dict[str, Any]: Словарь с информацией о тестах
    """
    if not os.path.exists(junit_file):
        logger.warning(f"Файл {junit_file} не найден")
        return {}
    
    try:
        tree = ET.parse(junit_file)
        root = tree.getroot()
        
        result = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "error": 0,
            "time": 0.0,
            "test_types": {},
            "failures": [],
            "slow_tests": []
        }
        
        # Собираем общую статистику
        for testsuite in root.findall(".//testsuite"):
            tests = int(testsuite.get("tests", 0))
            failures = int(testsuite.get("failures", 0))
            errors = int(testsuite.get("errors", 0))
            skipped = int(testsuite.get("skipped", 0))
            time = float(testsuite.get("time", 0))
            
            result["total"] += tests
            result["failed"] += failures + errors
            result["skipped"] += skipped
            result["passed"] += tests - failures - errors - skipped
            result["time"] += time
            
            # Определяем тип теста по имени
            test_type = testsuite.get("name", "").split(".")[-1].replace("test_", "")
            if test_type not in result["test_types"]:
                result["test_types"][test_type] = {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "time": 0.0
                }
            
            result["test_types"][test_type]["total"] += tests
            result["test_types"][test_type]["failed"] += failures + errors
            result["test_types"][test_type]["skipped"] += skipped
            result["test_types"][test_type]["passed"] += tests - failures - errors - skipped
            result["test_types"][test_type]["time"] += time
            
            # Собираем информацию о неудачных тестах
            for testcase in testsuite.findall(".//testcase"):
                test_name = testcase.get("name", "Unknown")
                test_class = testcase.get("classname", "Unknown")
                test_time = float(testcase.get("time", 0))
                
                # Добавляем в список медленных тестов
                result["slow_tests"].append({
                    "name": f"{test_class}.{test_name}",
                    "time": test_time,
                    "status": "passed"
                })
                
                # Проверяем неудачные тесты
                failure = testcase.find("failure")
                error = testcase.find("error")
                skipped_tag = testcase.find("skipped")
                
                if failure is not None or error is not None:
                    result["failures"].append({
                        "name": f"{test_class}.{test_name}",
                        "message": (failure.get("message") if failure is not None 
                                   else error.get("message", "Unknown error")),
                        "traceback": (failure.text if failure is not None 
                                     else error.text)
                    })
                    # Обновляем статус медленного теста
                    for slow_test in result["slow_tests"]:
                        if slow_test["name"] == f"{test_class}.{test_name}":
                            slow_test["status"] = "failed"
                            break
                elif skipped_tag is not None:
                    # Обновляем статус медленного теста
                    for slow_test in result["slow_tests"]:
                        if slow_test["name"] == f"{test_class}.{test_name}":
                            slow_test["status"] = "skipped"
                            break
        
        # Сортируем медленные тесты по времени (от большего к меньшему)
        result["slow_tests"].sort(key=lambda x: x["time"], reverse=True)
        # Оставляем только топ 10
        result["slow_tests"] = result["slow_tests"][:10]
        
        return result
    except Exception as e:
        logger.error(f"Ошибка при парсинге файла {junit_file}: {e}")
        return {}


def parse_coverage_xml(coverage_file: str) -> Dict[str, Any]:
    """
    Парсит Coverage XML файл с информацией о покрытии кода
    
    Args:
        coverage_file: Путь к Coverage XML файлу
        
    Returns:
        Dict[str, Any]: Словарь с информацией о покрытии кода
    """
    if not os.path.exists(coverage_file):
        logger.warning(f"Файл {coverage_file} не найден")
        return {}
    
    try:
        tree = ET.parse(coverage_file)
        root = tree.getroot()
        
        result = {
            "total_lines": 0,
            "covered_lines": 0,
            "missed_lines": 0,
            "coverage_percentage": 0.0,
            "modules": []
        }
        
        # Собираем общую статистику
        for package in root.findall(".//package"):
            for module in package.findall("classes/class"):
                module_name = module.get("name", "Unknown")
                module_result = {
                    "name": module_name,
                    "total_lines": 0,
                    "covered_lines": 0,
                    "missed_lines": 0,
                    "coverage_percentage": 0.0
                }
                
                for line in module.findall(".//line"):
                    module_result["total_lines"] += 1
                    result["total_lines"] += 1
                    
                    if line.get("hits", "0") != "0":
                        module_result["covered_lines"] += 1
                        result["covered_lines"] += 1
                    else:
                        module_result["missed_lines"] += 1
                        result["missed_lines"] += 1
                
                if module_result["total_lines"] > 0:
                    module_result["coverage_percentage"] = round(
                        module_result["covered_lines"] / module_result["total_lines"] * 100, 2)
                
                result["modules"].append(module_result)
        
        if result["total_lines"] > 0:
            result["coverage_percentage"] = round(
                result["covered_lines"] / result["total_lines"] * 100, 2)
        
        # Сортируем модули по покрытию (от меньшего к большему)
        result["modules"].sort(key=lambda x: x["coverage_percentage"])
        
        return result
    except Exception as e:
        logger.error(f"Ошибка при парсинге файла {coverage_file}: {e}")
        return {}


def parse_performance_results() -> Dict[str, Any]:
    """
    Собирает результаты нагрузочного тестирования
    
    Returns:
        Dict[str, Any]: Словарь с информацией о нагрузочных тестах
    """
    performance_dir = os.path.join(PROJECT_DIR, "performance")
    os.makedirs(performance_dir, exist_ok=True)
    
    result = {
        "tests": []
    }
    
    # Ищем JSON файлы с результатами в директории performance
    for file in os.listdir(performance_dir):
        if file.endswith(".json"):
            try:
                with open(os.path.join(performance_dir, file), "r") as f:
                    data = json.load(f)
                    
                    # Проверяем, что это файл с результатами нагрузочных тестов
                    if "requests" in data and "successful" in data:
                        test_name = file.replace(".json", "")
                        
                        # Добавляем дополнительную информацию
                        data["name"] = test_name
                        data["success_rate"] = round(data["successful"] / data["requests"] * 100, 2) if data["requests"] > 0 else 0
                        
                        result["tests"].append(data)
            except Exception as e:
                logger.error(f"Ошибка при парсинге файла {file}: {e}")
    
    return result


def generate_html_report(test_results: Dict[str, Any], coverage_data: Dict[str, Any], 
                         performance_data: Dict[str, Any], output_file: str) -> None:
    """
    Генерирует HTML отчет о тестировании
    
    Args:
        test_results: Данные о результатах тестов
        coverage_data: Данные о покрытии кода
        performance_data: Данные о результатах нагрузочного тестирования
        output_file: Путь к файлу, в который будет записан отчет
    """
    # Формируем HTML для таблицы с типами тестов
    test_types_rows = ""
    for test_type, data in test_results.get("test_types", {}).items():
        test_types_rows += f"""
        <tr>
            <td>{test_type}</td>
            <td>{data['total']}</td>
            <td>{data['passed']}</td>
            <td>{data['failed']}</td>
            <td>{data['skipped']}</td>
            <td>{data['time']:.2f}</td>
        </tr>
        """
    
    # Формируем HTML для неуспешных тестов
    failed_tests_content = ""
    if not test_results.get("failures"):
        failed_tests_content = "<p>Все тесты успешно пройдены!</p>"
    else:
        for failure in test_results.get("failures", []):
            failed_tests_content += f"""
            <div>
                <h3>{failure['name']}</h3>
                <p><strong>Сообщение:</strong> {failure['message']}</p>
                <pre>{failure['traceback']}</pre>
            </div>
            """
    
    # Формируем HTML для медленных тестов
    slow_tests_rows = ""
    for test in test_results.get("slow_tests", []):
        status_class = "success" if test["status"] == "passed" else "failure"
        slow_tests_rows += f"""
        <tr>
            <td>{test['name']}</td>
            <td>{test['time']:.4f}</td>
            <td class="{status_class}">{test['status']}</td>
        </tr>
        """
    
    # Формируем HTML для покрытия кода
    coverage_rows = ""
    for module in coverage_data.get("modules", []):
        coverage_percentage = module["coverage_percentage"]
        status_class = "success" if coverage_percentage >= 80 else "warning" if coverage_percentage >= 50 else "failure"
        coverage_rows += f"""
        <tr>
            <td>{module['name']}</td>
            <td class="{status_class}">{coverage_percentage:.2f}%</td>
            <td>{module['covered_lines']}</td>
            <td>{module['missed_lines']}</td>
        </tr>
        """
    
    # Формируем HTML для нагрузочного тестирования
    performance_results = ""
    if not performance_data.get("tests"):
        performance_results = "<p>Нет данных о нагрузочном тестировании</p>"
    else:
        performance_results += """
        <table>
            <tr>
                <th>Тест</th>
                <th>Запросов</th>
                <th>Успешно</th>
                <th>Неуспешно</th>
                <th>Успешность (%)</th>
                <th>Время (сек)</th>
                <th>Запросов/сек</th>
            </tr>
        """
        for test in performance_data.get("tests", []):
            success_rate = test.get("success_rate", 0)
            status_class = "success" if success_rate >= 90 else "warning" if success_rate >= 70 else "failure"
            performance_results += f"""
            <tr>
                <td>{test.get("name", "Unknown")}</td>
                <td>{test.get("requests", 0)}</td>
                <td>{test.get("successful", 0)}</td>
                <td>{test.get("failed", 0)}</td>
                <td class="{status_class}">{success_rate:.2f}%</td>
                <td>{test.get("total_time", 0):.2f}</td>
                <td>{test.get("requests_per_second", 0):.2f}</td>
            </tr>
            """
        performance_results += "</table>"
    
    # Расчет общей статистики
    total_tests = test_results.get("total", 0)
    passed_tests = test_results.get("passed", 0)
    failed_tests = test_results.get("failed", 0)
    skipped_tests = test_results.get("skipped", 0)
    
    pass_percentage = round(passed_tests / total_tests * 100, 2) if total_tests > 0 else 0
    
    # Статистика покрытия
    coverage_percentage = coverage_data.get("coverage_percentage", 0)
    covered_lines = coverage_data.get("covered_lines", 0)
    missed_lines = coverage_data.get("missed_lines", 0)
    
    # Статистика времени
    total_time = test_results.get("time", 0)
    avg_test_time = round(total_time / total_tests, 4) if total_tests > 0 else 0
    slowest_test_time = test_results.get("slow_tests", [{}])[0].get("time", 0) if test_results.get("slow_tests") else 0
    
    # Формируем HTML отчет
    html_report = HTML_TEMPLATE.format(
        generation_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_tests=total_tests,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        skipped_tests=skipped_tests,
        pass_percentage=pass_percentage,
        coverage_percentage=coverage_percentage,
        covered_lines=covered_lines,
        missed_lines=missed_lines,
        total_time=round(total_time, 2),
        avg_test_time=avg_test_time,
        slowest_test_time=slowest_test_time,
        test_types_rows=test_types_rows,
        failed_tests_content=failed_tests_content,
        slow_tests_rows=slow_tests_rows,
        coverage_rows=coverage_rows,
        performance_results=performance_results
    )
    
    # Записываем HTML отчет в файл
    with open(output_file, "w") as f:
        f.write(html_report)
    
    logger.info(f"HTML отчет сохранен в {output_file}")


def generate_json_report(test_results: Dict[str, Any], coverage_data: Dict[str, Any], 
                         performance_data: Dict[str, Any], output_file: str) -> None:
    """
    Генерирует JSON отчет о тестировании
    
    Args:
        test_results: Данные о результатах тестов
        coverage_data: Данные о покрытии кода
        performance_data: Данные о результатах нагрузочного тестирования
        output_file: Путь к файлу, в который будет записан отчет
    """
    # Формируем общий отчет
    report = {
        "generation_time": datetime.datetime.now().isoformat(),
        "test_results": test_results,
        "coverage_data": coverage_data,
        "performance_data": performance_data
    }
    
    # Записываем JSON отчет в файл
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"JSON отчет сохранен в {output_file}")


def main():
    """Основная функция скрипта"""
    parser = argparse.ArgumentParser(description="Генерация отчетов о тестировании WinDI Messenger")
    
    parser.add_argument("--test-type", "-t", choices=["unit", "integration", "e2e", "performance", "all"], 
                      default="all", help="Тип тестов для запуска")
    
    parser.add_argument("--run-tests", "-r", action="store_true", 
                      help="Запустить тесты перед генерацией отчета")
    
    parser.add_argument("--output", "-o", 
                      help="Имя файла отчета (без расширения)")
    
    args = parser.parse_args()
    
    # Создаем директорию для отчетов
    reports_dir = ensure_reports_dir()
    
    # Определяем имя файла отчета
    output_name = args.output or f"test_report_{args.test_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    html_output = os.path.join(reports_dir, f"{output_name}.html")
    json_output = os.path.join(reports_dir, f"{output_name}.json")
    
    # Запускаем тесты, если нужно
    if args.run_tests:
        exit_code, junit_xml, coverage_xml = run_pytest_with_reports(args.test_type)
        logger.info(f"Тесты выполнены с кодом возврата {exit_code}")
    else:
        # Используем последние отчеты
        junit_xml = os.path.join(reports_dir, f"{args.test_type}_results.xml")
        coverage_xml = os.path.join(reports_dir, f"{args.test_type}_coverage.xml")
    
    # Собираем данные для отчета
    test_results = parse_junit_xml(junit_xml)
    coverage_data = parse_coverage_xml(coverage_xml)
    performance_data = parse_performance_results()
    
    # Генерируем отчеты
    generate_html_report(test_results, coverage_data, performance_data, html_output)
    generate_json_report(test_results, coverage_data, performance_data, json_output)
    
    logger.info(f"Отчеты успешно сгенерированы: {html_output} и {json_output}")


if __name__ == "__main__":
    main() 