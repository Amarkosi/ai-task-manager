import os
import requests
import logging
from celery import Celery
from groq import Groq


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

GROQ_API_KEY = "8680723773:AAHeLosWb9sSgNrGxnQBFh68OZt_tNcitOc"
API_URL = "http://backend:8000/tasks"

ai_client = Groq(api_key=GROQ_API_KEY)


@celery_app.task(name="tasks.process_voice_task")
def process_voice_task(user_id: int, file_bytes_list: list, file_name: str):
    """Фоновая задача для расшифровки аудио и отправки в бэкенд"""
    logging.info(f"Началась фоновая обработка файла {file_name} для пользователя {user_id}")

    local_path = f"/tmp/{file_name}"
    with open(local_path, "wb") as f:
        f.write(bytes(file_bytes_list))

    try:
        # Отправляем в Whisper (Groq)
        with open(local_path, "rb") as audio_file:
            translation = ai_client.audio.transcriptions.create(
                file=(file_name, audio_file.read(), "audio/ogg"),
                model="whisper-large-v3",
                language="ru"
            )

        recognized_text = translation.text
        if not recognized_text.strip():
            logging.warning("Речь не распознана.")
            return "Речь не распознана"

        task_data = {
            "user_id": user_id,
            "title": recognized_text[:50] + "..." if len(recognized_text) > 50 else recognized_text,
            "description": f"🎙️ Фоновая голосовая задача: {recognized_text}"
        }

        response = requests.post(API_URL, json=task_data)
        logging.info(f"Задача отправлена на бэкенд. Статус: {response.status_code}")
        return recognized_text

    except Exception as e:
        logging.error(f"Ошибка в воркере: {e}")
        return str(e)

    finally:
        if os.path.exists(local_path):
            os.remove(local_path)