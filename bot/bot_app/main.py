import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command

# Импортируем настроенную Celery-задачу
# ИСПРАВЛЕНО: Полный путь импорта для Celery-воркера
from tasks import process_voice_task

BOT_TOKEN = os.getenv("BOT_TOKEN")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")
API_URL = os.getenv("API_URL", "http://backend:8000")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 🚀\n\n"
        "Отправь мне текст или запиши голос, чтобы создать задачу.\n"
        "Команда /board выдаст ссылку на твою Канбан-доску."
    )

@dp.message(Command("board"))
async def cmd_board(message: types.Message):
    user_url = f"{FRONTEND_URL}/?user_id={message.from_user.id}"
    await message.answer(f"📋 Твоя личная Канбан-доска:\n{user_url}")

# ВЫПОЛНЕНИЕ ТЗ: Асинхронная отправка голоса в Redis-очередь
@dp.message(lambda message: message.voice)
async def handle_voice_task(message: types.Message, bot: Bot):
    # Мгновенный фидбек пользователю по ТЗ (UX: Speed of transcription feedback)
    await message.answer("🔄 Голос принят! Задача добавлена в фоновую очередь Redis на ИИ-расшифровку...")
    
    # Скачиваем файл из Telegram в память
    voice_file_id = message.voice.file_id
    file = await bot.get_file(voice_file_id)
    file_io = await bot.download_file(file.file_path)
    audio_bytes = file_io.read()

    # Сериализуем байты в список чисел для передачи через Redis в Celery
    bytes_list = list(audio_bytes)
    file_name = f"voice_{message.from_user.id}_{message.message_id}.ogg"

    # Отправляем в воркер! Бот моментально свободен.
    process_voice_task.delay(message.from_user.id, bytes_list, file_name)

# Обработка быстрых текстовых заметок
@dp.message(lambda message: message.text)
async def handle_text_task(message: types.Message):
    user_url = f"{FRONTEND_URL}/?user_id={message.from_user.id}"
    task_data = {
        "user_id": message.from_user.id,
        "title": message.text,
        "description": "Создано через Telegram"
    }
    try:
        response = requests.post(f"{API_URL}/tasks", json=task_data, timeout=5)
        if response.status_code == 201:
            await message.answer(f"✅ Задача успешно создана и добавлена на доску!\n{user_url}")
        else:
            await message.answer(f"❌ Ошибка бэкенда: {response.status_code}")
    except Exception as e:
        logging.error(f"Backend connection error: {e}")
        await message.answer("❌ Не удалось связаться с сервером бэкенда.")

async def main():
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
