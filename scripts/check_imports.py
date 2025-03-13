#!/usr/bin/env python
"""
Скрипт для проверки путей импорта в исходном коде проекта.
Ищет импорты устаревших модулей и предлагает заменить их на новые.
"""
import os
import re
from collections import defaultdict

# Пути файлов, которые нужно проверить
PATHS_TO_CHECK = [
    "app",
    "tests",
    "scripts",
    "migrations",
]

# Шаблоны импортов, которые нужно заменить
IMPORT_PATTERNS = [
    {
        "old": r"from app\.services\.user_service import get_current_user",
        "new": "from app.api.dependencies import get_current_user",
        "message": "Функция get_current_user перемещена в app.api.dependencies"
    }
]

# Игнорируемые файлы (эти файлы были удалены)
IGNORED_FILES = []

def scan_file(file_path):
    """Сканирует файл на наличие устаревших импортов"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    for pattern in IMPORT_PATTERNS:
        for match in re.finditer(pattern["old"], content):
            module = match.group(1)
            issues.append({
                "file": file_path,
                "line": content[:match.start()].count('\n') + 1,
                "old_import": match.group(0),
                "new_import": pattern["new"].format(module.lower(), module),
                "message": pattern["message"].format(module.lower())
            })
    
    return issues

def scan_directory(directory):
    """Рекурсивно сканирует директорию на наличие Python файлов"""
    issues = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if file_path not in IGNORED_FILES:
                    issues.extend(scan_file(file_path))
    return issues

def main():
    """Основная функция скрипта"""
    all_issues = []
    for path in PATHS_TO_CHECK:
        if os.path.isdir(path):
            all_issues.extend(scan_directory(path))
        elif os.path.isfile(path) and path.endswith('.py'):
            all_issues.extend(scan_file(path))
    
    # Группировка проблем по файлам
    issues_by_file = defaultdict(list)
    for issue in all_issues:
        issues_by_file[issue["file"]].append(issue)
    
    # Вывод результатов
    if not all_issues:
        print("Отлично! Устаревших импортов не найдено.")
        return
    
    print(f"Найдено {len(all_issues)} проблем с импортами в {len(issues_by_file)} файлах:")
    print()
    
    for file, issues in issues_by_file.items():
        print(f"Файл: {file}")
        for issue in issues:
            print(f"  Строка {issue['line']}: {issue['old_import']}")
            print(f"  Рекомендация: {issue['message']}")
            print(f"  Замена: {issue['new_import']}")
            print()

if __name__ == "__main__":
    main() 