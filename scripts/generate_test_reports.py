#!/usr/bin/env python3
"""
Скрипт для генерации различных отчетов о тестировании
"""
import os
import subprocess
import argparse
import json
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

# Директория проекта
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPORTS_DIR = os.path.join(PROJECT_DIR, "test_reports")


def ensure_reports_dir():
    """Проверяет наличие директории для отчетов и создает ее при необходимости"""
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
        print(f"Создана директория для отчетов: {REPORTS_DIR}")


def run_coverage_report():
    """Запускает тесты и генерирует отчет о покрытии кода"""
    print("Запуск тестов с генерацией отчета о покрытии кода...")
    
    # Запускаем тесты с покрытием
    result = subprocess.run([
        "pytest",
        "tests/unit/",
        "tests/integration/",
        "--cov=app",
        "--cov-report=term",
        "--cov-report=html"
    ], cwd=PROJECT_DIR)
    
    if result.returncode != 0:
        print("\nОшибка выполнения тестов!")
        return False
    
    # Копируем отчет в нашу директорию
    report_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    coverage_dir = os.path.join(REPORTS_DIR, f"coverage_{report_time}")
    
    if not os.path.exists(coverage_dir):
        os.makedirs(coverage_dir)
    
    # Копируем htmlcov в нашу директорию отчетов
    subprocess.run(["cp", "-r", "htmlcov", coverage_dir], cwd=PROJECT_DIR)
    
    print(f"\nОтчет о покрытии кода сохранен в: {coverage_dir}/htmlcov")
    return True


def run_performance_report():
    """Запускает нагрузочные тесты и генерирует отчет о производительности"""
    print("Запуск нагрузочных тестов и генерация отчета о производительности...")
    
    # Запускаем тесты производительности
    result = subprocess.run([
        "pytest",
        "tests/performance/",
        "-v"
    ], cwd=PROJECT_DIR, env={**os.environ, "FULL_LOAD_TEST": "1"})
    
    if result.returncode != 0:
        print("\nОшибка выполнения нагрузочных тестов!")
        return False
    
    # Ищем файлы с результатами нагрузочных тестов
    load_files = []
    for file in os.listdir(PROJECT_DIR):
        if file.startswith("load_test_") and file.endswith(".json"):
            load_files.append(file)
    
    if not load_files:
        print("Файлы с результатами нагрузочных тестов не найдены!")
        return False
    
    # Создаем директорию для отчета
    report_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    performance_dir = os.path.join(REPORTS_DIR, f"performance_{report_time}")
    
    if not os.path.exists(performance_dir):
        os.makedirs(performance_dir)
    
    # Собираем данные и генерируем графики
    report_data = []
    
    for file in load_files:
        with open(os.path.join(PROJECT_DIR, file), "r") as f:
            data = json.load(f)
            summary = data["summary"]
            
            # Извлекаем тип запроса и конкурентность из имени файла
            parts = file.split("_")
            request_type = parts[2]
            concurrency = int(parts[3].split(".")[0][1:])
            
            report_data.append({
                "request_type": request_type,
                "concurrency": concurrency,
                "success_rate": summary["success_rate"],
                "avg_request_time": summary["avg_request_time"],
                "requests_per_second": summary["requests_per_second"],
                "p90_request_time": summary["p90_request_time"],
                "p95_request_time": summary["p95_request_time"],
                "p99_request_time": summary["p99_request_time"]
            })
        
        # Копируем исходный файл в директорию отчета
        subprocess.run(["cp", file, performance_dir], cwd=PROJECT_DIR)
    
    # Преобразуем данные в DataFrame для удобства обработки
    df = pd.DataFrame(report_data)
    
    # Сохраняем сводную таблицу
    df.to_csv(os.path.join(performance_dir, "summary.csv"), index=False)
    
    # Генерируем графики
    plot_performance_graphs(df, performance_dir)
    
    print(f"\nОтчет о производительности сохранен в: {performance_dir}")
    return True


def plot_performance_graphs(df, output_dir):
    """Генерирует графики на основе данных о производительности"""
    # График среднего времени запроса по типам и конкурентности
    plt.figure(figsize=(10, 6))
    for request_type in df["request_type"].unique():
        subset = df[df["request_type"] == request_type]
        plt.plot(subset["concurrency"], subset["avg_request_time"], 
                marker='o', label=f"{request_type}")
    
    plt.title("Среднее время запроса по типам и конкурентности")
    plt.xlabel("Конкурентность")
    plt.ylabel("Среднее время запроса (сек)")
    plt.grid(True)
    plt.legend()
    plt.savefig(os.path.join(output_dir, "avg_request_time.png"))
    
    # График запросов в секунду по типам и конкурентности
    plt.figure(figsize=(10, 6))
    for request_type in df["request_type"].unique():
        subset = df[df["request_type"] == request_type]
        plt.plot(subset["concurrency"], subset["requests_per_second"], 
                marker='o', label=f"{request_type}")
    
    plt.title("Запросов в секунду по типам и конкурентности")
    plt.xlabel("Конкурентность")
    plt.ylabel("Запросов в секунду")
    plt.grid(True)
    plt.legend()
    plt.savefig(os.path.join(output_dir, "requests_per_second.png"))
    
    # График процентилей времени запроса
    plt.figure(figsize=(10, 6))
    percentiles = ["avg_request_time", "p90_request_time", "p95_request_time", "p99_request_time"]
    
    for request_type in df["request_type"].unique():
        plt.figure(figsize=(10, 6))
        subset = df[df["request_type"] == request_type]
        
        for percentile in percentiles:
            plt.plot(subset["concurrency"], subset[percentile], 
                    marker='o', label=f"{percentile}")
        
        plt.title(f"Процентили времени запроса для {request_type}")
        plt.xlabel("Конкурентность")
        plt.ylabel("Время запроса (сек)")
        plt.grid(True)
        plt.legend()
        plt.savefig(os.path.join(output_dir, f"percentiles_{request_type}.png"))


def main():
    """Основная функция скрипта"""
    parser = argparse.ArgumentParser(description="Генерация отчетов о тестировании")
    
    # Выбор типа отчета
    parser.add_argument("report_type", choices=["coverage", "performance", "all"], 
                      help="Тип отчета для генерации")
    
    args = parser.parse_args()
    
    # Проверяем наличие директории для отчетов
    ensure_reports_dir()
    
    if args.report_type == "coverage" or args.report_type == "all":
        run_coverage_report()
    
    if args.report_type == "performance" or args.report_type == "all":
        run_performance_report()
    

if __name__ == "__main__":
    main() 