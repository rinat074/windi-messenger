#!/usr/bin/env python
"""
Скрипт для заполнения базы данных тестовыми данными.
Запуск: python seed_db.py
"""
import asyncio
from app.utils.seed_data import seed_all

if __name__ == "__main__":
    print("Заполнение базы данных тестовыми данными...")
    asyncio.run(seed_all())
    print("Заполнение базы данных завершено!") 