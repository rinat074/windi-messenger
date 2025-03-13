"""
Модуль настроек приложения
"""
import os
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, BaseSettings, Field, validator


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Основные настройки проекта
    PROJECT_NAME: str = "WinDI Messenger"
    PROJECT_DESCRIPTION: str = "Мессенджер с поддержкой мультиустройственности и WebSocket"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Настройки окружения
    ENVIRONMENT: str = "development"
    DEBUG: bool = Field(default=False)
    
    # Настройки безопасности
    SECRET_KEY: str = "your-secret-key-here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 дней
    ALGORITHM: str = "HS256"
    ALLOW_CREDENTIALS: bool = True
    
    # Настройки CORS
    CORS_ORIGINS: Union[List[AnyHttpUrl], List[str]] = Field(default=["http://localhost:3000"])
    
    # Настройки базы данных
    DATABASE_URI: str = "postgresql+asyncpg://postgres:password@localhost:5432/windi"
    DATABASE_POOL_SIZE: int = 50
    
    # Настройки Redis
    REDIS_URI: str = "redis://redis:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    
    # Настройки хранения файлов
    MEDIA_ROOT: str = "/app/media"
    MEDIA_URL: str = "/media/"
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_MIME_TYPES: List[str] = [
        "image/jpeg", "image/png", "image/gif", 
        "audio/mpeg", "audio/wav", "audio/ogg", 
        "video/mp4", "video/webm",
        "application/pdf", "application/msword", 
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel", 
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain"
    ]
    
    # Настройки мониторинга
    ENABLE_MONITORING: bool = True
    MONITORING_INTERVAL: int = 300  # 5 минут
    MEMORY_THRESHOLD_MB: int = 500
    CPU_THRESHOLD_PERCENT: int = 70
    
    # Настройки логирования
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DIR: str = "./logs"
    
    # Настройки безопасности запросов
    RATE_LIMIT_DEFAULT: int = 100  # Запросов в минуту по умолчанию
    RATE_LIMIT_LOGIN: int = 10     # Ограничение на попытки входа
    MAX_LOGIN_ATTEMPTS: int = 5    # Максимальное число неудачных попыток входа
    LOGIN_ATTEMPT_TIMEOUT: int = 15 * 60  # 15 минут блокировки после превышения
    
    # Настройки метрик Prometheus
    METRICS_ENABLED: bool = True
    METRICS_PATH: str = "/metrics"
    
    # Настройки Centrifugo
    CENTRIFUGO_URL: str = "http://centrifugo:8000"
    CENTRIFUGO_API_KEY: str = "change-this-to-a-long-random-string-in-production"
    CENTRIFUGO_TOKEN_SECRET: str = "change-this-to-a-long-random-string-in-production"
    CENTRIFUGO_TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24  # 24 часа
    
    # Настройки для очистки данных
    CLEANUP_INTERVAL: int = 24 * 60 * 60  # 24 часа
    SESSION_CLEANUP_DAYS: int = 30  # 30 дней
    
    @validator("SECRET_KEY", pre=True)
    def validate_secret_key(cls, v: str) -> str:
        """Проверяет, что SECRET_KEY заменен в продакшене"""
        if os.environ.get("ENVIRONMENT", "").lower() == "production":
            if v == "your-secret-key-here":
                raise ValueError("В продакшен-окружении SECRET_KEY должен быть заменен")
        return v
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """Преобразует строку CORS_ORIGINS в список"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    class Config:
        """Настройки для чтения переменных окружения"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        # Схема Pydantic для валидации .env файла
        @classmethod
        def schema_extra(cls, schema: Dict[str, Any]) -> None:
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)


# Создание объекта настроек
settings = Settings()

# Проверка наличия необходимых переменных окружения
if settings.ENVIRONMENT.lower() == "production":
    assert settings.SECRET_KEY != "your-secret-key-here", "Необходимо установить SECRET_KEY для production" 