from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Build the SQLAlchemy engine on first use so tests can import the module
    without a reachable database."""
    url = settings.database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
    return create_engine(url, **kwargs)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def SessionLocal():  # type: ignore[invalid-name]
    """Compatibility shim — call as `SessionLocal()` to obtain a session."""
    return get_session_factory()()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
