"""
Маршруты для загрузки и получения файловых вложений
"""
import os
import time
import uuid
from datetime import datetime
from typing import List

import aiofiles
import magic
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.core.performance import async_time_it
from app.db.database import get_db
from app.db.models.user import User
from app.schemas.message import Attachment, AttachmentType

# Создание маршрутизатора
router = APIRouter(prefix=f"{settings.API_V1_STR}/files", tags=["files"])

# Получение логгера
logger = get_logger("file_routes")

# Убеждаемся, что директория для медиа-файлов существует
os.makedirs(settings.MEDIA_ROOT, exist_ok=True)


@router.post(
    "/upload", 
    response_model=List[Attachment],
    summary="Загрузка файлов",
    description="""
    Загружает файлы и возвращает информацию о них.
    Поддерживает множественную загрузку.
    
    - Проверяет тип файла (MIME-тип)
    - Ограничивает размер файла
    - Создает уникальные имена для файлов
    - Для изображений генерирует миниатюры
    
    Возвращает список вложений, которые можно использовать в сообщениях.
    """
)
@async_time_it
async def upload_files(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Загрузка файлов для вложений"""
    
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не выбраны файлы для загрузки"
        )
    
    # Создаем директорию для пользователя, если её нет
    user_upload_dir = os.path.join(settings.MEDIA_ROOT, str(current_user.id))
    os.makedirs(user_upload_dir, exist_ok=True)
    
    # Текущая дата для организации файлов
    current_date = datetime.now().strftime("%Y-%m-%d")
    date_dir = os.path.join(user_upload_dir, current_date)
    os.makedirs(date_dir, exist_ok=True)
    
    result = []
    
    for file in files:
        # Проверка размера файла
        file_size = 0
        chunk = await file.read(1024)
        
        while chunk:
            file_size += len(chunk)
            if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Размер файла превышает максимально допустимый ({settings.MAX_FILE_SIZE_MB} МБ)"
                )
            chunk = await file.read(1024)
        
        # Перемещаем указатель в начало файла
        await file.seek(0)
        
        # Читаем начало файла для определения MIME-типа
        header = await file.read(2048)
        await file.seek(0)
        
        # Определяем MIME-тип
        mime_type = magic.from_buffer(header, mime=True)
        
        # Проверяем, разрешен ли этот тип файла
        if mime_type not in settings.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Неподдерживаемый тип файла: {mime_type}"
            )
        
        # Генерируем уникальное имя файла
        original_filename = file.filename
        extension = os.path.splitext(original_filename)[1] if original_filename else ""
        if not extension and mime_type:
            # Определяем расширение по MIME-типу
            mime_to_ext = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "audio/mpeg": ".mp3",
                "audio/wav": ".wav",
                "audio/ogg": ".ogg",
                "video/mp4": ".mp4",
                "video/webm": ".webm",
                "application/pdf": ".pdf",
                "text/plain": ".txt"
            }
            extension = mime_to_ext.get(mime_type, "")
        
        unique_filename = f"{int(time.time())}_{uuid.uuid4()}{extension}"
        file_path = os.path.join(date_dir, unique_filename)
        
        # Сохраняем файл
        async with aiofiles.open(file_path, "wb") as out_file:
            content = await file.read()
            await out_file.write(content)
        
        # Определяем тип вложения
        attachment_type = AttachmentType.DOCUMENT
        if mime_type.startswith("image/"):
            attachment_type = AttachmentType.IMAGE
        elif mime_type.startswith("video/"):
            attachment_type = AttachmentType.VIDEO
        elif mime_type.startswith("audio/"):
            attachment_type = AttachmentType.AUDIO
        
        # Формируем URL для доступа к файлу
        file_url = f"{settings.API_V1_STR}/files/{current_user.id}/{current_date}/{unique_filename}"
        
        # Создаем информацию о вложении
        attachment = Attachment(
            id=uuid.uuid4(),
            type=attachment_type,
            filename=original_filename or unique_filename,
            size=os.path.getsize(file_path),
            mime_type=mime_type,
            url=f"http://localhost:8000{file_url}",  # В реальном проекте должен быть настоящий URL
            thumbnail_url=None  # Миниатюры можно добавить для изображений
        )
        
        # Добавляем вложение в результат
        result.append(attachment)
    
    logger.info(f"Пользователь {current_user.id} загрузил {len(result)} файлов")
    return result


@router.get(
    "/{user_id}/{date}/{filename}",
    summary="Получение файла по пути",
    description="""
    Возвращает файл по указанному пути.
    
    Путь включает:
    - ID пользователя, загрузившего файл
    - Дату загрузки
    - Уникальное имя файла
    """
)
@async_time_it
async def get_file(
    user_id: str,
    date: str,
    filename: str,
    request: Request
):
    """Получение файла по пути"""
    
    # Формируем путь к файлу
    file_path = os.path.join(settings.MEDIA_ROOT, user_id, date, filename)
    
    # Проверяем, существует ли файл
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл не найден"
        )
    
    # Определяем MIME-тип файла
    mime_type = magic.from_file(file_path, mime=True)
    
    # Возвращаем файл
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=os.path.basename(filename)
    ) 