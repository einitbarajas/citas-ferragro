"""Migraciones SQL idempotentes (producción Render no ejecuta db/init automáticamente)."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Orden importa: columnas de notificaciones antes de auditoría.
_MIGRATION_FILES = (
    "022_notificaciones_actor_auditoria.sql",
    "024_audit_actor_role.sql",
)


def _migrations_dir() -> Path:
    # backend/app/db/schema_upgrade.py -> repo root/db/init
    return Path(__file__).resolve().parents[3] / "db" / "init"


def apply_pending_sql_migrations(engine: Engine) -> None:
    base = _migrations_dir()
    if not base.is_dir():
        logger.warning("Carpeta de migraciones no encontrada: %s", base)
        return

    with engine.begin() as conn:
        for name in _MIGRATION_FILES:
            path = base / name
            if not path.is_file():
                logger.warning("Migración omitida (no existe): %s", path)
                continue
            sql = path.read_text(encoding="utf-8").strip()
            if not sql:
                continue
            logger.info("Aplicando migración SQL: %s", name)
            conn.execute(text(sql))
    logger.info("Migraciones SQL de notificaciones/auditoría verificadas")
