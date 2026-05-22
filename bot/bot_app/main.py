import asyncio
import logging
import os
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command

# Токены и адреса
BOT_TOKEN = os.getenv("BOT_TOKEN", "8680723773:AAHeLosWb9sSgNrGxnQBFh68OZt_tNcitOc")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vercel.app")
API_URL = os.getenv("API_URL", "https://onrender.com")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

async def async_voice_processing(message: types.Message, bot: Bot, user_url: str):
    try:
        voice_file_id = message.voice.file_id
        file = await bot.get_file(voice_file_id)
        local_path = f"{voice_file_id}.ogg"
        await bot.download_file(file.file_path, local_path)

        # Отправляем аудио в стабильный ИИ-шлюз OpenAI Whisper
        headers = {"Authorization": "Bearer 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"}
        with open(local_path, "rb") as f:
            files = {
                "file": (local_path, f, "audio/ogg"),
                "model": (None, "openai/whisper-1")
            }
            # Используем выделенный прокси-сервер OpenAI для мгновенной расшифровки
            response = requests.post("https://openrouter.ai", headers=headers, files=files)
        
        if os.path.exists(local_path):
            os.remove(local_path)

        if response.status_code == 200:
            text_result = response.json().get("text", "").strip()
            
            if not text_result:
                await message.answer("❌ ИИ не смог расслышать речь в этом аудио. Попробуйте надиктовать четче.")
                return

            # Записываем настоящие слова в PostgreSQL базу Neon
            task_data = {
                "user_id": message.from_user.id,
                "title": text_result,
                "description": "Создано голосом через Telegram"
            }
            api_resp = requests.post(API_URL, json=task_data)
            
            if api_resp.status_code == 201:
                await message.answer(
                    f"✅ Голосовая задача успешно создана!\n\n"
                    f"Текст задачи: \"{text_result}\"\n\n"
                    f"Результат уже на доске:\n{user_url}"
                )
            else:
                await message.answer(f"❌ Текст распознан: \"{text_result}\", но бэкенд вернул ошибку {api_resp.status_code}")
        else:
            logging.error(f"ИИ Error: {response.text}")
            await message.answer("❌ Временная задержка на стороне ИИ-декодера OpenAI. Попробуйте еще раз.")
            
    except Exception as e:
        logging.error(f"Ошибка фоновой обработки аудио: {e}")
        await message.answer("❌ Произошла ошибка при обработке голосового сообщения.")

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
        "📥 Ваше аудио принято в очередь! ИИ обрабатывает его в фоне.\n\n"
        f"Следите за обновлениями на доске:\n{user_url}"
    )
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
