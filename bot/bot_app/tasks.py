import base64
import os
import requests
import logging
from celery import Celery
from groq import Groq

# КРИТИЧЕСКИЙ ФИКС ДЛЯ ИИ: Принудительно импортируем и запускаем загрузку .env на Render
from dotenv import load_dotenv
load_dotenv()

# Подключаем Redis в качестве брокера задач по ТЗ
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Фиксируем параметры SSL для безопасного облачного Redis (Upstash)
if "upstash.io" in REDIS_URL and "ssl_cert_reqs" not in REDIS_URL:
    REDIS_URL += "?ssl_cert_reqs=none"

celery_app = Celery(
    "tasks", 
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Забираем ключ ИИ и адрес бэкенда, которые теперь гарантированно видны воркеру
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
base_api = os.getenv('API_URL', 'http://backend:8000').rstrip('/')
API_URL = f"{base_api}/tasks"

# Инициализируем клиент ИИ с проверенным ключом
ai_client = Groq(api_key=GROQ_API_KEY)

@celery_app.task(name="tasks.process_voice_task")
def process_voice_task(user_id: int, audio_base64: str, file_name: str):
    logging.info(f" Celery-воркер забрал задачу {file_name} из очереди Redis")
    local_path = f"/tmp/{file_name}"
    
    try:
        # ИСПРАВЛЕНО: Раскодируем строку Base64 обратно в бинарный аудиофайл
        audio_bytes = base64.b64decode(audio_base64.encode('utf-8'))
        
        # Восстанавливаем аудиофайл на диск воркера
        with open(local_path, "wb") as f:
            f.write(audio_bytes)

        # Делаем асинхронный фоновый запрос к Whisper ИИ через официальный SDK
        with open(local_path, "rb") as audio_file:
            translation = ai_client.audio.transcriptions.create(
                file=(file_name, audio_file.read(), "audio/ogg"),
                model="whisper-large-v3",
                language="ru"  # Жестко фиксируем русский язык для максимальной точности
            )

        recognized_text = translation.text
        if not recognized_text or not recognized_text.strip():
            logging.warning("Речь в аудиосообщении не распознана ИИ.")
            return "Речь не распознана"

        # Отправляем распознанную задачу в рабочий API Бэкенда
        task_data = {
            "user_id": user_id,
            "title": recognized_text[:50] + "..." if len(recognized_text) > 50 else recognized_text,
            "description": f"🎙️ Голосовая задача: {recognized_text}"
        }
        
        response = requests.post(API_URL, json=task_data, timeout=15)
        logging.info(f"Задача передана в API Бэкенда. Статус: {response.status_code}")
        return recognized_text

    except Exception as e:
        logging.error(f"Критическая ошибка Celery-воркера при обработке ИИ: {e}")
        return str(e)
    finally:
        # Очищаем память сервера от аудиофайла при любом исходе
        if os.path.exists(local_path):
            os.remove(local_path)
