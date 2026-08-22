"""Database engine and session helpers."""

from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.core.config import settings

engine: Engine = settings._app_db_engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with Session(engine) as session:
        yield session
