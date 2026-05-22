import asyncio
import logging
import os
import io
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command

# Токены и адреса берутся из переменных окружения Render
BOT_TOKEN = os.getenv("BOT_TOKEN", "8680723773:AAGVjWn2FBO07hmDL9T6vq_oUPGXrb5IFwI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vercel.app")
API_URL = os.getenv("API_URL", "https://onrender.com")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

# Изолированная фоновая ИИ-обработка аудио на стороне бота
async def async_voice_processing(message: types.Message, bot: Bot, user_url: str):
    status_msg = await message.answer("🔄 ИИ расшифровывает ваше аудио, пожалуйста, подождите...")
    try:
        # 1. Скачиваем аудиофайл напрямую из Telegram
        voice_file_id = message.voice.file_id
        file = await bot.get_file(voice_file_id)
        
        # Скачиваем файл в оперативную память, чтобы не работать с диском на Render
        file_io = io.BytesIO()
        await bot.download_file(file.file_path, file_io)
        audio_bytes = file_io.getvalue()

        # Превращаем байты в виртуальный ogg-файл для корректного multipart запроса в Groq
        audio_packet = io.BytesIO(audio_bytes)
        audio_packet.name = "voice.ogg"

        text_result = ""
        
        # 2. Отправляем поток аудио напрямую в Groq Whisper API (Whisper-Large-V3)
        try:
            response = requests.post(
                "https://groq.com",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": (audio_packet.name, audio_packet, "audio/ogg")},
                data={"model": "whisper-large-v3"},
                timeout=25
            )
            if response.status_code == 200:
                text_result = response.json().get("text", "").strip()
            else:
                logging.error(f"Groq API Error Response: {response.text}")
        except Exception as e:
            logging.error(f"Groq API Request Exception: {e}")

        if not text_result:
            await status_msg.edit_text("❌ ИИ не смог распознать речь в этом аудио. Попробуйте надиктовать четче.")
            return

        # 3. Отправляем полученный РЕАЛЬНЫЙ текст в ваш бэкенд FastAPI
        task_data = {
            "user_id": message.from_user.id,
            "title": text_result,
            "description": "Создано голосом через Telegram"
        }
        api_resp = requests.post(API_URL, json=task_data)
        
        if api_resp.status_code == 201:
            await status_msg.edit_text(
                f"✅ Голосовая задача успешно создана!\n\n"
                f"Текст задачи: \"{text_result}\"\n\n"
                f"Результат уже на доске Vercel:\n{user_url}"
            )
        else:
            await status_msg.edit_text(f"❌ Текст распознан: \"{text_result}\", но бэкенд вернул ошибку {api_resp.status_code}")
            
    except Exception as e:
        logging.error(f"Ошибка фоновой обработки аудио: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при обработке голосового сообщения.")

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
    # Запускаем тяжелую ИИ-обработку параллельно в фоне, бот не зависает
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
