"""
Сквозной тест основного сценария работы с чатом
"""
import pytest
import asyncio
import logging
import uuid

logger = logging.getLogger("e2e_tests")

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_chat_creation_and_messaging(user_session, second_user_session):
    """
    Тест проверяет основной сценарий работы с чатом:
    1. Создание группового чата первым пользователем
    2. Отправка сообщения в чат
    3. Чтение сообщений вторым пользователем
    4. Ответ на сообщение вторым пользователем
    """
    # Генерируем уникальное имя чата для теста
    chat_name = f"E2E Test Chat {uuid.uuid4()}"
    
    # 1. Первый пользователь создает чат
    chat_id = await user_session.create_chat(chat_name)
    assert chat_id is not None, "Не удалось создать чат"
    logger.info(f"Создан новый чат: {chat_id}")
    
    # Проверяем, что чат появился в списке чатов пользователя
    await user_session.load_chats()
    chat_found = any(chat.get("id") == chat_id for chat in user_session.chats)
    assert chat_found, "Созданный чат не найден в списке чатов пользователя"
    
    # 2. Первый пользователь отправляет сообщение
    message_text = f"Привет! Это тестовое сообщение {uuid.uuid4()}"
    message = await user_session.send_message(chat_id, message_text)
    assert message is not None, "Не удалось отправить сообщение"
    assert message.get("text") == message_text, "Текст отправленного сообщения не совпадает"
    logger.info(f"Отправлено сообщение: {message.get('id')}")
    
    # Даем время на обработку сообщения
    await asyncio.sleep(1)
    
    # 3. Второй пользователь получает список чатов
    await second_user_session.load_chats()
    
    # Проверяем, есть ли созданный чат в списке чатов второго пользователя
    # Если чат не доступен второму пользователю, нужно добавить его
    chat_found = any(chat.get("id") == chat_id for chat in second_user_session.chats)
    if not chat_found:
        logger.info("Чат не найден у второго пользователя, добавляем пользователя в чат")
        # Для этого нужно реализовать метод добавления пользователя в чат
        # Так как это e2e тест, мы используем API напрямую
        
        # Получаем информацию о чате
        async with user_session.client as client:
            response = await client.get(f"/api/v1/chats/{chat_id}")
            assert response.status_code == 200, "Не удалось получить информацию о чате"
        
        # Добавляем второго пользователя в чат (здесь должна быть логика API)
        async with user_session.client as client:
            response = await client.post(
                f"/api/v1/chats/{chat_id}/users",
                json={"user_id": second_user_session.user_id}
            )
            # Проверяем статус, но не критично если API возвращает ошибку,
            # так как пользователь может уже быть в чате
            if response.status_code not in (200, 201, 409):
                logger.warning(f"Не удалось добавить пользователя в чат: {response.status_code}")
        
        # Обновляем список чатов
        await second_user_session.load_chats()
    
    # 4. Второй пользователь получает сообщения чата
    messages = await second_user_session.get_messages(chat_id)
    assert messages is not None, "Не удалось получить сообщения чата"
    assert len(messages) > 0, "Список сообщений пуст"
    
    # Проверяем, что сообщение от первого пользователя получено
    found_message = False
    for msg in messages:
        if msg.get("text") == message_text:
            found_message = True
            break
    
    assert found_message, f"Сообщение '{message_text}' не найдено в истории чата"
    logger.info("Сообщение найдено в истории чата")
    
    # 5. Второй пользователь отвечает на сообщение
    reply_text = f"Ответное сообщение от второго пользователя {uuid.uuid4()}"
    reply = await second_user_session.send_message(chat_id, reply_text)
    assert reply is not None, "Не удалось отправить ответное сообщение"
    logger.info(f"Отправлен ответ: {reply.get('id')}")
    
    # Даем время на обработку сообщения
    await asyncio.sleep(1)
    
    # 6. Первый пользователь проверяет историю и видит ответ
    updated_messages = await user_session.get_messages(chat_id)
    assert updated_messages is not None, "Не удалось получить обновленные сообщения чата"
    
    # Проверяем, что ответное сообщение получено
    found_reply = False
    for msg in updated_messages:
        if msg.get("text") == reply_text:
            found_reply = True
            break
    
    assert found_reply, f"Ответное сообщение '{reply_text}' не найдено в истории чата"
    logger.info("Ответное сообщение найдено в истории чата")
    
    # Тест пройден успешно
    logger.info("Сценарий чата выполнен успешно!") 