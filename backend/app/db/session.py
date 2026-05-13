import os

os.environ.setdefault("PGCLIENTENCODING", "UTF8")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _postgresql_psycopg_url(url: str) -> str:
    """Use psycopg3 driver; avoids psycopg2/libpq UTF-8 decode issues on Windows (e.g. Py 3.14)."""
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql+psycopg2://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def _engine_connect_args(url: str) -> dict[str, str]:
    if settings.is_production and "localhost" not in url and "127.0.0.1" not in url and "sslmode=" not in url:
        return {"sslmode": "require"}
    return {}


engine = create_engine(
    _postgresql_psycopg_url(settings.database_url),
    connect_args=_engine_connect_args(settings.database_url),
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
