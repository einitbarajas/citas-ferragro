import pytest
import psycopg

from app.core.config import settings


@pytest.fixture
def db():
    """Conexion a PostgreSQL; cada prueba corre en una transaccion que se revierte al terminar."""
    conn = psycopg.connect(settings.database_url, autocommit=False)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
