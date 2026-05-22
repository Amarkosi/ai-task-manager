import asyncio
import logging
import os
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from tasks import process_voice_task

BOT_TOKEN = "8680723773:AAHeLosWb9sSgNrGxnQBFh68OZt_tNcitOc"

# Адаптивные адреса
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
API_URL = os.getenv("API_URL", "http://backend:8000/tasks")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 🚀\n\n"
        "Пожалуйста, введите или нажмите команду /board, чтобы получить ссылку на вашу личную Канбан-доску."
    )


@dp.message(Command("board"))
async def cmd_board(message: types.Message):
    user_url = f"{FRONTEND_URL}/?user_id={message.from_user.id}"
    await message.answer(user_url)


@dp.message(lambda message: message.voice)
async def handle_voice_task(message: types.Message, bot: Bot):
    user_url = f"{FRONTEND_URL}/?user_id={message.from_user.id}"
    await message.answer(
        "📥 Ваше аудио принято в очередь! ИИ обработает его в фоне.\n\n"
        f"Следите за обновлениями на доске:\n{user_url}"
    )

    voice_file_id = message.voice.file_id
    file = await bot.get_file(voice_file_id)
    local_path = f"{voice_file_id}.ogg"
    await bot.download_file(file.file_path, local_path)

    with open(local_path, "rb") as f:
        file_bytes = list(f.read())

    process_voice_task.delay(message.from_user.id, file_bytes, local_path)
    if os.path.exists(local_path):
        os.remove(local_path)


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