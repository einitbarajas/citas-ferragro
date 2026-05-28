"""Purga automática de notificaciones antiguas (retención por días)."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user_notification import UserNotification

logger = logging.getLogger(__name__)


def run_notification_purge_batch() -> int:
    days = max(1, int(settings.notification_retention_days))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted = 0
    with SessionLocal() as db:
        result = db.execute(delete(UserNotification).where(UserNotification.created_at < cutoff))
        # rowcount puede ser None en algunos drivers; normalizamos
        deleted = int(getattr(result, "rowcount", 0) or 0)
        if deleted:
            db.commit()
    if deleted:
        logger.info("Notificaciones purgadas (>%s días): %s", days, deleted)
    return deleted


async def notification_purge_scheduler_loop(stop_event: asyncio.Event) -> None:
    interval = max(300, int(settings.notification_purge_interval_seconds))
    while True:
        try:
            run_notification_purge_batch()
        except Exception:
            logger.exception("Error en scheduler de purga de notificaciones")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break

