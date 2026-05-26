import sys
import os
import base64
import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv

# Корректируем пути Python до импортов, чтобы файлы в bot_app видели друг друга напрямую
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Загружаем переменные и импортируем Celery-задачу
load_dotenv()
from tasks import process_voice_task

BOT_TOKEN = os.getenv("BOT_TOKEN")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")
API_URL = os.getenv("API_URL", "http://backend:8000")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

# ДОБАВЛЕНО: Бесплатный авто-пинг бэкенда каждые 5 минут, чтобы сервер никогда не спал
async def keep_backend_alive():
    logging.info("🤖 Фоновая задача авто-пинга бэкенда запущена")
    while True:
        try:
            base_url = API_URL.rstrip('/')
            # Просто пингуем главную страницу нашего бэкенда методом GET
            response = requests.get(f"{base_url}/", timeout=10)
            logging.info(f"🤖 Авто-пинг бэкенда выполнен. Статус ответа: {response.status_code}")
        except Exception as e:
            logging.error(f"🤖 Ошибка авто-пинга бэкенда: {e}")
        
        # Засыпаем ровно на 5 минут (300 секунд) перед следующим пингом
        await asyncio.sleep(300)

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

@dp.message(lambda message: message.voice)
async def handle_voice_task(message: types.Message, bot: Bot):
    user_url = f"{FRONTEND_URL}/?user_id={message.from_user.id}"
    await message.answer(
        "🔄 Голосовое сообщение принято и добавлено в фоновую очередь Redis на ИИ-расшифровку!\n\n"
        f"📋 Результат появится на вашей доске через пару секунд без перезагрузки:\n{user_url}"
    )
    
    voice_file_id = message.voice.file_id
    file = await bot.get_file(voice_file_id)
    file_io = await bot.download_file(file.file_path)
    audio_bytes = file_io.read()

    # Сжимаем бинарный звук в легкую текстовую строку Base64 для стабильной работы Celery/Redis
    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    file_name = f"voice_{message.from_user.id}_{message.message_id}.ogg"

    # Отправляем в воркер
    process_voice_task.delay(message.from_user.id, audio_base64, file_name)

@dp.message(lambda message: message.text)
async def handle_text_task(message: types.Message):
    user_url = f"{FRONTEND_URL}/?user_id={message.from_user.id}"
    task_data = {
        "user_id": message.from_user.id,
        "title": message.text,
        "description": "Создано через Telegram"
    }
    
    try:
        base_url = API_URL.rstrip('/')
        tasks_endpoint = f"{base_url}/tasks"
        
        response = requests.post(tasks_endpoint, json=task_data, timeout=10)
        
        if response.status_code == 201:
            await message.answer(
                "✅ Текстовая задача создана!\n\n"
                f"Посмотреть результат можно на вашей доске:\n{user_url}"
            )
        elif response.status_code == 405:
            backup_response = requests.post(f"{tasks_endpoint}/", json=task_data, timeout=10)
            if backup_response.status_code == 201:
                await message.answer(
                    "✅ Текстовая задача создана!\n\n"
                    f"Посмотреть результат можно на вашей доске:\n{user_url}"
                )
            else:
                await message.answer(f"❌ Сервер вернул ошибку при повторном запросе: {backup_response.status_code}")
        else:
            await message.answer(f"❌ Сервер бэкенда вернул ошибку: {response.status_code}")
            
    except Exception as e:
        logging.error(f"Backend connection error: {e}")
        await message.answer("❌ Не удалось связаться с сервером бэкенда.")

async def main():
    if not BOT_TOKEN:
        raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не задан!")
    bot = Bot(token=BOT_TOKEN)
    
    # ДОБАВЛЕНО: Запускаем бесконечный фоновый цикл будильника одновременно со стартом бота
    asyncio.create_task(keep_backend_alive())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
