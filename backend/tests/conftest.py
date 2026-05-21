import pytest
import psycopg
from sqlalchemy.orm import Session

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


@pytest.fixture
def db_session():
    """Sesion SQLAlchemy; rollback al cerrar (no persiste datos de prueba)."""
    from app.db.session import SessionLocal

    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
