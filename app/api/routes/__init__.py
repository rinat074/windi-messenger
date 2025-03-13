"""
Модуль с маршрутами API приложения
"""
from fastapi import APIRouter

from app.api.routes import user_routes
from app.api.routes import chat_routes
from app.api.routes import history_routes
from app.api.routes import session_routes
from app.api.routes import file_routes
from app.api.routes import search_routes
from app.api.routes import monitoring_routes
from app.api.routes import centrifugo_routes

# Создаем основной роутер API
api_router = APIRouter()

# Включаем все необходимые роутеры
api_router.include_router(user_routes.router)
api_router.include_router(chat_routes.router)
api_router.include_router(history_routes.router)
api_router.include_router(session_routes.router)
api_router.include_router(file_routes.router)
api_router.include_router(search_routes.router)
api_router.include_router(monitoring_routes.router)
api_router.include_router(centrifugo_routes.router) 