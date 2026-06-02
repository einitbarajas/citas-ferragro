"""Migraciones SQL idempotentes al arranque (Render rootDir=backend, sin ../db/init del repo)."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_MIGRATION_FILES = (
    "022_notificaciones_actor_auditoria.sql",
    "024_audit_actor_role.sql",
)

# Siempre ejecutable en producción (ADD COLUMN IF NOT EXISTS).
_CRITICAL_COLUMN_SQL = """
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "IdBodega" INTEGER;
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "IdProveedorCita" NUMERIC(10, 0);
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "IdActor" VARCHAR(30);
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "RolActor" VARCHAR(30);
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "EtiquetaActor" VARCHAR(200);
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "Accion" VARCHAR(40);
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "EstadoCita" VARCHAR(30);
ALTER TABLE "HistorialCambios" ADD COLUMN IF NOT EXISTS "IpOrigen" VARCHAR(45);
ALTER TABLE "HistorialCambios" ADD COLUMN IF NOT EXISTS "RolActor" VARCHAR(30);
"""


def _migrations_dirs() -> list[Path]:
    backend_root = Path(__file__).resolve().parents[2]
    candidates = [
        backend_root / "db" / "init",
        backend_root.parent / "db" / "init",
    ]
    return [p for p in candidates if p.is_dir()]


def apply_pending_sql_migrations(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in _CRITICAL_COLUMN_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))
        logger.info("Columnas críticas de notificaciones/auditoría verificadas")

        applied_files = False
        for base in _migrations_dirs():
            for name in _MIGRATION_FILES:
                path = base / name
                if not path.is_file():
                    continue
                sql = path.read_text(encoding="utf-8").strip()
                if not sql:
                    continue
                logger.info("Aplicando migración SQL: %s (%s)", name, path.parent.name)
                conn.execute(text(sql))
                applied_files = True
        if not applied_files:
            logger.warning(
                "Archivos 022/024 no encontrados en disco; solo se aplicaron ALTER inline"
            )
