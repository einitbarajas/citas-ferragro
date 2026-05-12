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


engine = create_engine(_postgresql_psycopg_url(settings.database_url), future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
