from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


url = get_settings().database_url
kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
if url in {"sqlite://", "sqlite:///:memory:"}:
    kwargs["poolclass"] = StaticPool
engine = create_engine(url, **kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

