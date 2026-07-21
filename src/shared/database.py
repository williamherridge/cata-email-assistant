"""Database engine and session helpers."""

from collections.abc import Generator
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.shared.config import get_settings


settings = get_settings()
logger = logging.getLogger(__name__)

connect_args = {"check_same_thread": False} if settings.resolved_database_url.startswith("sqlite") else {}
engine = create_engine(settings.resolved_database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session for request-scoped work."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        logger.exception("Rolling back request-scoped database session after an unhandled error.")
        raise
    finally:
        session.close()
