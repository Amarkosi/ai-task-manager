import asyncio
import logging
import os
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command

BOT_TOKEN = os.getenv("BOT_TOKEN", "8680723773:AAHeLosWb9sSgNrGxnQBFh68OZt_tNcitOc")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vercel.app")
API_URL = os.getenv("API_URL", "https://onrender.com")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

async def async_voice_processing(message: types.Message, bot: Bot, user_url: str):
    status_msg = await message.answer("🔄 Обработка аудио на сервере, пожалуйста, подождите...")
    try:
        voice_file_id = message.voice.file_id
        file = await bot.get_file(voice_file_id)
        local_path = f"{voice_file_id}.ogg"
        await bot.download_file(file.file_path, local_path)
        
        voice_api_url = API_URL.replace("/tasks", "/tasks/voice") if API_URL.endswith("/tasks") else f"{API_URL}/voice"
        
        with open(local_path, "rb") as f:
            files = {"file": (local_path, f, "audio/ogg")}
            data = {"user_id": str(message.from_user.id)}
            response = requests.post(voice_api_url, files=files, data=data)
        
        if os.path.exists(local_path):
            os.remove(local_path)

        if response.status_code == 201:
            text_result = response.json().get("title", "").strip()
            await status_msg.edit_text(
                f"✅ Голосовая задача успешно создана!\n\n"
                f"Текст задачи: \"{text_result}\"\n\n"
                f"Результат уже на доске Vercel:\n{user_url}"
            )
        else:
            logging.error(f"Backend voice error: {response.text}")
            await status_msg.edit_text("❌ Бэкенд не смог распознать аудио. Попробуйте надиктовать четче.")
            
    except Exception as e:
        logging.error(f"Ошибка обработки аудио: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при обработке голосового сообщения.")

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 🚀\n\n"
        "Я ваш Omni-Channel ассистент. Чтобы создать задачу, вы можете:\n"
        "1. Написать её текстом в этот чат.\n"
        "2. Нажать значок микрофона 🎙 на клавиатуре вашего телефона и надиктовать её голосом (она автоматически переведется в текст)!\n\n"
        "Посмотреть вашу Канбан-доску можно по команде /board"
    )

@dp.message(Command("board"))
async def cmd_board(message: types.Message):
    user_url = f"{FRONTEND_URL}/?user_id={message.from_user.id}"
    await message.answer(user_url)

@dp.message(lambda message: message.voice)
async def handle_voice_task(message: types.Message, bot: Bot):
    user_url = f"{FRONTEND_URL}/?user_id={message.from_user.id}"
    asyncio.create_task(async_voice_processing(message, bot, user_url))

@dp.message(lambda message: message.text)
async def handle_text_task(message: types.Message):
    user_url = f"{FRONTEND_URL}/?user_id={message.from_user.id}"
    task_data = {
        "user_id": message.from_user.id,
        "title": message.text,
        "description": "Создано через Telegram-бота"
    }
    try:
        response = requests.post(API_URL, json=task_data)
        if response.status_code == 201:
            await message.answer(
                "✅ Текстовая задача создана!\n\n"
                f"Посмотреть результат можно на вашей доске:\n{user_url}"
            )
        else:
            await message.answer(f"❌ Сервер бэкенда вернул ошибку: {response.status_code}")
    except Exception as e:
        logging.error(f"Ошибка связи с бэкендом: {e}")
        await message.answer("❌ Ошибка связи с бэкендом.")

async def main():
    bot = Bot(token=BOT_TOKEN)
    from aiogram.types import BotCommand, BotCommandScopeDefault
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="board", description="🔗 Получить ссылку на мою доску")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
