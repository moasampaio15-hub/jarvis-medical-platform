from collections.abc import Generator

from sqlalchemy.orm import Session

from app.database.connection import get_session_factory


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        yield session
