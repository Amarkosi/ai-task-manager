import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# URL для локального подключения к PostgreSQL из Docker
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/task_db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
