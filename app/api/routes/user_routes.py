from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_response
from app.core.config import settings
from app.core.logging import get_logger
from app.core.performance import async_time_it
from app.core.session import session_manager
from app.db.database import get_db
from app.schemas.session import DeviceRegistrationRequest
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserResponse
from app.services.user_service import UserService

# Создание маршрутизатора
router = APIRouter(prefix=f"{settings.API_V1_STR}/users", tags=["users"])

# Получение логгера
logger = get_logger("user_routes")


@router.post(
    "/register", 
    response_model=UserResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
    description="""
    Регистрирует нового пользователя в системе.
    
    - Принимает данные пользователя: имя, email и пароль
    - Проверяет, что пользователь с таким email еще не зарегистрирован
    - Хеширует пароль для безопасного хранения
    - Создает нового пользователя в базе данных
    
    Возвращает данные созданного пользователя (без пароля).
    """
)
@async_time_it
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация нового пользователя
    
    Принимает имя, email и пароль пользователя. Проверяет, что пользователь с таким
    email не существует. Создает нового пользователя с хешированным паролем.
    """
    user_service = UserService(db)
    user = await user_service.create_user(user_data)
    
    logger.info(f"Зарегистрирован новый пользователь: {user.email}")
    
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email
    )


@router.post(
    "/login", 
    response_model=Token,
    summary="Аутентификация пользователя",
    description="""
    Выполняет аутентификацию пользователя и выдает JWT токен.
    
    - Принимает email (в поле username) и пароль
    - Проверяет правильность учетных данных
    - Генерирует JWT токен для доступа к защищенным ресурсам
    
    Возвращает токен доступа и его тип.
    """
)
@async_time_it
async def login_user(
    response: Response,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    device_data: DeviceRegistrationRequest = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Аутентификация пользователя и получение токена
    
    Принимает email (в поле username) и пароль через стандартную форму OAuth2.
    Проверяет правильность учетных данных. Возвращает JWT токен для аутентификации.
    """
    user_service = UserService(db)
    user = await user_service.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        logger.warning(f"Неудачная попытка входа для пользователя: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Создание токена
    access_token = user_service.create_access_token(user.id)
    
    # Создание сессии для нового устройства
    device_name = "Неизвестное устройство"
    if device_data and device_data.device_name:
        device_name = device_data.device_name
        
    # Получение информации о клиенте
    ip_address = request.client.host
    user_agent = request.headers.get("User-Agent", "Unknown")
    
    # Создание сессии
    session_id = session_manager.create_session(
        user_id=str(user.id),
        device_name=device_name,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    # Устанавливаем cookie с ID сессии
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=settings.ENVIRONMENT.lower() == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    logger.info(f"Пользователь {user.email} успешно вошел в систему (устройство: {device_name})")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        session_id=session_id
    )


@router.get(
    "/me", 
    response_model=UserResponse,
    summary="Получение информации о текущем пользователе",
    description="""
    Возвращает информацию о текущем аутентифицированном пользователе.
    
    - Извлекает пользователя из JWT токена, предоставленного в заголовке Authorization
    - Возвращает основные данные пользователя
    
    Требует валидный токен с правильным форматом 'Bearer {token}'.
    """
)
@async_time_it
async def get_user_me(
    current_user: UserResponse = Depends(get_current_user_response)
):
    """
    Получение информации о текущем аутентифицированном пользователе
    
    Извлекает информацию о текущем пользователе из токена авторизации.
    Требует валидный токен в заголовке Authorization.
    """
    logger.debug(f"Запрос информации о пользователе: {current_user.id}")
    return current_user


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Выход из системы",
    description="""
    Выполняет выход пользователя из системы.
    
    - Завершает текущую сессию пользователя
    - Удаляет cookie с ID сессии
    
    После успешного выхода пользователю потребуется повторная авторизация.
    """
)
@async_time_it
async def logout_user(
    response: Response,
    request: Request,
    current_user: UserResponse = Depends(get_current_user_response)
):
    """
    Выход пользователя из системы
    
    Завершает текущую сессию и удаляет cookie с ID сессии.
    """
    # Получаем ID текущей сессии из cookie
    session_id = request.cookies.get("session_id")
    
    if session_id:
        # Завершаем сессию
        session_manager.terminate_session(session_id)
        
        # Удаляем cookie
        response.delete_cookie(
            key="session_id", 
            httponly=True,
            secure=settings.ENVIRONMENT.lower() == "production",
            samesite="lax"
        )
    
    logger.info(f"Пользователь {current_user.id} вышел из системы")
    
    return {"message": "Вы успешно вышли из системы"} 