#!/usr/bin/env python3
"""
Скрипт для поиска неиспользуемых импортов в Python файлах проекта.

Использование:
    python scripts/find_unused_imports.py [директория]
    
    По умолчанию сканирует директорию app/.
"""
import os
import sys
import ast
from typing import List, Dict, Set, Any

# Цвета для вывода в терминал
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def get_python_files(directory: str) -> List[str]:
    """Получает список всех Python файлов в директории и поддиректориях"""
    python_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    return python_files


class ImportVisitor(ast.NodeVisitor):
    """AST-визитор для анализа импортов и их использования"""
    
    def __init__(self):
        self.imports = {}  # {имя: модуль}
        self.from_imports = {}  # {имя: модуль}
        self.used_names = set()  # имена, которые используются
        
    def visit_Import(self, node):
        """Обрабатывает инструкции 'import module'"""
        for name in node.names:
            if name.asname:
                self.imports[name.asname] = name.name
            else:
                self.imports[name.name] = name.name
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        """Обрабатывает инструкции 'from module import name'"""
        module = node.module
        for name in node.names:
            if name.asname:
                self.from_imports[name.asname] = (module, name.name)
            else:
                self.from_imports[name.name] = (module, name.name)
        self.generic_visit(node)
        
    def visit_Name(self, node):
        """Обрабатывает использование имен переменных"""
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)
        
    def visit_Attribute(self, node):
        """Обрабатывает атрибуты (module.attribute)"""
        if isinstance(node.value, ast.Name):
            # Если обращение к атрибуту импортированного модуля
            self.used_names.add(node.value.id)
        self.generic_visit(node)


def analyze_file(file_path: str) -> Dict[str, List[str]]:
    """Анализирует файл и возвращает неиспользуемые импорты"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
        visitor = ImportVisitor()
        visitor.visit(tree)
        
        unused_imports = []
        
        # Проверяем обычные импорты
        for name, module in visitor.imports.items():
            if name not in visitor.used_names:
                unused_imports.append(f"import {module}" + 
                                    (f" as {name}" if name != module else ""))
        
        # Проверяем импорты from
        for name, (module, orig_name) in visitor.from_imports.items():
            if name not in visitor.used_names:
                unused_imports.append(f"from {module} import {orig_name}" +
                                    (f" as {name}" if name != orig_name else ""))
        
        return {
            "file": file_path,
            "unused_imports": unused_imports
        }
    except SyntaxError:
        return {
            "file": file_path,
            "error": "Синтаксическая ошибка в файле"
        }


def main():
    """Основная функция скрипта"""
    directory = "app"
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    
    if not os.path.isdir(directory):
        print(f"{Colors.FAIL}Ошибка: {directory} не является директорией{Colors.ENDC}")
        sys.exit(1)
    
    print(f"{Colors.HEADER}Сканирование директории: {directory}{Colors.ENDC}")
    
    python_files = get_python_files(directory)
    print(f"{Colors.OKBLUE}Найдено {len(python_files)} Python файлов{Colors.ENDC}")
    
    total_unused_imports = 0
    files_with_unused_imports = 0
    
    for file in python_files:
        result = analyze_file(file)
        
        if "error" in result:
            print(f"{Colors.WARNING}[!] {result['file']}: {result['error']}{Colors.ENDC}")
            continue
        
        if result["unused_imports"]:
            files_with_unused_imports += 1
            total_unused_imports += len(result["unused_imports"])
            
            print(f"{Colors.BOLD}{result['file']}{Colors.ENDC}")
            for imp in result["unused_imports"]:
                print(f"  {Colors.FAIL}- {imp}{Colors.ENDC}")
            print()
    
    print(f"{Colors.HEADER}Итого:{Colors.ENDC}")
    print(f"{Colors.OKBLUE}Проверено файлов: {len(python_files)}{Colors.ENDC}")
    print(f"{Colors.WARNING}Файлов с неиспользуемыми импортами: {files_with_unused_imports}{Colors.ENDC}")
    print(f"{Colors.FAIL}Всего неиспользуемых импортов: {total_unused_imports}{Colors.ENDC}")
    
    if total_unused_imports > 0:
        print(f"\n{Colors.BOLD}Совет:{Colors.ENDC} Используйте инструменты autoflake или pyflakes для автоматического удаления.")
        print(f"Например: {Colors.OKGREEN}autoflake --remove-all-unused-imports --recursive --in-place {directory}/{Colors.ENDC}")


if __name__ == "__main__":
    main() 