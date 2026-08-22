import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

_database_url = settings.database_url
if _database_url.startswith("sqlite"):
    # Ensure the parent directory exists for file-based SQLite databases
    # like sqlite:///./connx_dev.db (in-memory URLs have no path).
    db_path = _database_url.split(":///", 1)[-1] if ":///" in _database_url else ""
    if db_path and not db_path.startswith(":memory:"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

engine = create_engine(
    _database_url,
    connect_args={"check_same_thread": False} if "sqlite" in _database_url else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
