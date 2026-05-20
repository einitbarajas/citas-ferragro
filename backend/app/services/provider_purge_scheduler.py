"""Purga automática de proveedores suspendidos tras el plazo configurado."""
import asyncio
import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.provider_account import providers_due_for_purge, purge_provider_account

logger = logging.getLogger(__name__)


def run_provider_purge_batch() -> int:
    purged = 0
    with SessionLocal() as db:
        due = providers_due_for_purge(db)
        for provider in due:
            nit = int(provider.nit)
            name = provider.company_name
            try:
                purge_provider_account(
                    db,
                    provider,
                    actor_id="sistema",
                    log_description=(
                        f"Purga automática tras suspensión: {name} (NIT {nit}). "
                        "Datos operativos y credencial eliminados; auditoría conservada."
                    ),
                    log_action="provider_purge_scheduled",
                    notify=True,
                )
                purged += 1
            except Exception:
                logger.exception("Error al purgar proveedor NIT %s", nit)
        if purged:
            db.commit()
    if purged:
        logger.info("Proveedores purgados automáticamente: %s", purged)
    return purged


async def provider_purge_scheduler_loop(stop_event: asyncio.Event) -> None:
    interval = max(300, int(settings.provider_purge_check_interval_seconds))
    while True:
        try:
            run_provider_purge_batch()
        except Exception:
            logger.exception("Error en scheduler de purga de proveedores")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            continue
