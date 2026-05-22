import traceback
import sys

try:
    from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, UploadFile, File, Form
    from fastapi.middleware.cors import CORSMiddleware
    from sqlalchemy.orm import Session
    from pydantic import BaseModel
    from typing import List, Optional, Dict
    import json
    import os
    import random
    import requests

    from backend_app.database import engine, Base, get_db
    from backend_app import models
except Exception as e:
    print("CRITICAL IMPORT ERROR DURING STARTUP:", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print("DATABASE CONNECTION ERROR DURING STARTUP:", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

app = FastAPI(title="AI Task Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except Exception:
                    pass

manager = ConnectionManager()

class TaskCreate(BaseModel):
    user_id: int
    title: str
    description: Optional[str] = None

class TaskStatusUpdate(BaseModel):
    status: str

class TaskResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    status: str

    class Config:
        from_attributes = True

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.telegram_id == task.user_id).first()
    if not db_user:
        new_user = models.User(telegram_id=task.user_id, username="tg_user", first_name="User")
        db.add(new_user)
        db.commit()

    db_task = models.Task(user_id=task.user_id, title=task.title, description=task.description)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    task_info = {
        "event": "task_created",
        "data": {
            "id": db_task.id,
            "user_id": db_task.user_id,
            "title": db_task.title,
            "description": db_task.description,
            "status": db_task.status
        }
    }
    await manager.send_personal_message(json.dumps(task_info), task.user_id)
    return db_task

@app.get("/tasks", response_model=List[TaskResponse])
def get_user_tasks(user_id: Optional[int] = None, db: Session = Depends(get_db)):
    if user_id is not None:
        return db.query(models.Task).filter(models.Task.user_id == user_id).all()
    return db.query(models.Task).all()

@app.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task_status(task_id: int, status_update: TaskStatusUpdate, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    db_task.status = status_update.status
    db.commit()
    db.refresh(db_task)

    task_info = {
        "event": "task_updated",
        "data": {
            "id": db_task.id,
            "status": db_task.status
        }
    }
    await manager.send_personal_message(json.dumps(task_info), db_task.user_id)
    return db_task

# --- ЗАМЕНИТЕ ТОЛЬКО ЭТУ ФУНКЦИЮ В САМОМ КОНЦЕ ФАЙЛА backend/backend_app/main.py ---
@app.post("/tasks/voice", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_voice_task(user_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    text_result = ""
    try:
        with open(temp_path, "rb") as f:
            audio_data = f.read()

        # Подключаем мощный ИИ-сервер Groq Whisper API (Whisper-Large-V3)
        response = requests.post(
            "https://groq.com",
            headers={"Authorization": "Bearer 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"},
            files={"file": (temp_path, audio_data, "audio/ogg"), "model": (None, "whisper-large-v3")},
            timeout=15
        )
        if response.status_code == 200:
            text_result = response.json().get("text", "").strip()
    except Exception as e:
        print(f"Groq API Error: {e}")

    if not text_result:
        text_result = "Новая голосовая задача"

    if os.path.exists(temp_path):
        os.remove(temp_path)

    db_user = db.query(models.User).filter(models.User.telegram_id == user_id).first()
    if not db_user:
        new_user = models.User(telegram_id=user_id, username="tg_user", first_name="User")
        db.add(new_user)
        db.commit()

    db_task = models.Task(user_id=user_id, title=text_result, description="Создано голосом через Telegram")
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    task_info = {
        "event": "task_created",
        "data": {
            "id": db_task.id,
            "user_id": db_task.user_id,
            "title": db_task.title,
            "description": db_task.description,
            "status": db_task.status
        }
    }
    await manager.send_personal_message(json.dumps(task_info), user_id)
    return db_task
