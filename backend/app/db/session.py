import os

os.environ.setdefault("PGCLIENTENCODING", "UTF8")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _postgresql_psycopg_url(url: str) -> str:
    """Use psycopg3 driver; avoids psycopg2/libpq UTF-8 decode issues on Windows (e.g. Py 3.14)."""
    normalized = url.strip()
    # Render y otros hosts entregan postgres:// (sin ql)
    if normalized.startswith("postgres://"):
        normalized = "postgresql://" + normalized.removeprefix("postgres://")
    if normalized.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + normalized.removeprefix("postgresql+psycopg2://")
    if normalized.startswith("postgresql://"):
        return "postgresql+psycopg://" + normalized.removeprefix("postgresql://")
    return normalized


def _engine_connect_args(url: str) -> dict[str, str]:
    args: dict[str, str] = {"connect_timeout": "15"}
    if settings.is_production and "localhost" not in url and "127.0.0.1" not in url and "sslmode=" not in url:
        args["sslmode"] = "require"
    return args


engine = create_engine(
    _postgresql_psycopg_url(settings.database_url),
    connect_args=_engine_connect_args(settings.database_url),
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
