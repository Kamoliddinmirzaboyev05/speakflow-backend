from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _normalize_db_url(url: str) -> str:
    """Make the DATABASE_URL usable by SQLAlchemy + psycopg3.

    Render hands out `postgres://...` (legacy scheme that SQLAlchemy 2.x
    rejects) and a bare `postgresql://...` defaults to psycopg2, which we don't
    ship. Force the psycopg (v3) driver, which has wheels for modern Python.
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize_db_url(settings.DATABASE_URL)
_is_sqlite = DATABASE_URL.startswith("sqlite")

# SQLite needs check_same_thread off for the threaded server; Postgres on
# Render's free tier drops idle connections, so pre-ping + recycle keep the
# pool healthy.
if _is_sqlite:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
