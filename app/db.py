import os
import time
from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://picture_rain:picture_rain_dev@db:5432/picture_rain",
)
ALEMBIC_CONFIG_PATH = Path(__file__).resolve().parent.parent / "alembic.ini"


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(max_attempts: int = 30) -> None:
    from app import models  # noqa: F401

    last_error: OperationalError | None = None
    for attempt in range(max_attempts):
        try:
            config = Config(str(ALEMBIC_CONFIG_PATH))
            config.set_main_option(
                "sqlalchemy.url", str(engine.url).replace("%", "%%")
            )
            command.upgrade(config, "head")
            return
        except OperationalError as error:
            last_error = error
            if attempt == max_attempts - 1:
                raise
            time.sleep(2)

    if last_error is not None:
        raise last_error


def check_db(session: Session) -> None:
    session.execute(text("SELECT 1"))


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
