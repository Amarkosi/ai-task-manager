import os
import requests
import logging
from celery import Celery
from groq import Groq

# Подключаем Redis в качестве брокера задач по ТЗ
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "tasks", 
    broker=REDIS_URL,
    backend=REDIS_URL
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
API_URL = f"{os.getenv('API_URL', 'http://backend:8000')}/tasks"

ai_client = Groq(api_key=GROQ_API_KEY)

@celery_app.task(name="tasks.process_voice_task")
def process_voice_task(user_id: int, file_bytes_list: list, file_name: str):
    logging.info(f" Celery-воркер забрал задачу {file_name} из очереди Redis")
    local_path = f"/tmp/{file_name}"
    
    try:
        # Восстанавливаем аудиофайл из переданного ботом списка байт
        with open(local_path, "wb") as f:
            f.write(bytes(file_bytes_list))

        # Делаем асинхронный фоновый запрос к Whisper ИИ
        with open(local_path, "rb") as audio_file:
            translation = ai_client.audio.transcriptions.create(
                file=(file_name, audio_file.read(), "audio/ogg"),
                model="whisper-large-v3",
                language="ru"
            )

        recognized_text = translation.text
        if not recognized_text or not recognized_text.strip():
            logging.warning("Речь не распознана.")
            return "Речь не распознана"

        # Отправляем распознанную задачу в наш обновленный API Бэкенда
        task_data = {
            "user_id": user_id,
            "title": recognized_text[:50] + "..." if len(recognized_text) > 50 else recognized_text,
            "description": f"🎙️ Голосовая задача: {recognized_text}"
        }
        
        response = requests.post(API_URL, json=task_data, timeout=10)
        logging.info(f"Задача передана в API. Статус бэкенда: {response.status_code}")
        return recognized_text

    except Exception as e:
        logging.error(f"Критическая ошибка Celery-воркера: {e}")
        return str(e)
    finally:
        # Очищаем память сервера от аудиофайла
        if os.path.exists(local_path):
            os.remove(local_path)