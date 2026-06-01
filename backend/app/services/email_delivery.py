"""Envío transaccional con reintentos, logs estructurados y preparación de transporte."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

from app.core.config import refresh_smtp_settings, settings

logger = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1.5


@dataclass(frozen=True)
class EmailDeliveryResult:
    ok: bool
    recipient: str
    subject: str
    kind: str
    provider: str
    attempts: int
    error: str | None = None


def prepare_mail_transport() -> bool:
    """Carga secretos y valida que exista al menos un canal de envío operativo."""
    from app.core.smtp_env_loader import overlay_render_smtp_secret
    from app.services.email_transport import email_delivery_ready, render_smtp_blocked
    from app.services.smtp_resolver import ensure_smtp_login_ready

    overlay_render_smtp_secret()
    refresh_smtp_settings()
    if settings.brevo_send_ready or settings.resend_send_ready:
        return True
    if not settings.is_production:
        return settings.smtp_send_ready
    if email_delivery_ready():
        return True
    if render_smtp_blocked():
        logger.error(
            "Transporte de correo no disponible: Render bloquea SMTP. "
            "Configura RESEND_API_KEY o BREVO_API_KEY."
        )
        return False
    if ensure_smtp_login_ready():
        return True
    return ensure_smtp_login_ready(force=True)


def active_email_provider_label() -> str:
    return settings.email_provider or "none"


def deliver_with_retry(
    send_once: Callable[[], bool],
    *,
    recipient: str,
    subject: str,
    kind: str,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> EmailDeliveryResult:
    """
    Ejecuta send_once hasta max_attempts veces tras preparar transporte.
    En producción refresca secretos en cada intento.
    """
    provider = active_email_provider_label()
    last_error: str | None = None

    for attempt in range(1, max(1, max_attempts) + 1):
        if not prepare_mail_transport():
            last_error = "mail_transport_not_ready"
            logger.warning(
                "email_delivery kind=%s attempt=%s/%s to=%s subject=%r error=%s",
                kind,
                attempt,
                max_attempts,
                recipient,
                subject,
                last_error,
            )
            if attempt < max_attempts and settings.is_production:
                time.sleep(RETRY_DELAY_SECONDS)
            continue

        provider = active_email_provider_label()
        try:
            if send_once():
                logger.info(
                    "email_delivery ok kind=%s provider=%s attempt=%s to=%s subject=%r",
                    kind,
                    provider,
                    attempt,
                    recipient,
                    subject,
                )
                from app.services.email_delivery_log import record_delivery

                record_delivery(
                    kind=kind,
                    to=recipient,
                    subject=subject,
                    provider=provider,
                    ok=True,
                    attempts=attempt,
                )
                return EmailDeliveryResult(
                    ok=True,
                    recipient=recipient,
                    subject=subject,
                    kind=kind,
                    provider=provider,
                    attempts=attempt,
                )
            last_error = "send_returned_false"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "email_delivery exception kind=%s attempt=%s to=%s",
                kind,
                attempt,
                recipient,
            )

        logger.warning(
            "email_delivery fail kind=%s provider=%s attempt=%s/%s to=%s subject=%r error=%s",
            kind,
            provider,
            attempt,
            max_attempts,
            recipient,
            subject,
            last_error,
        )
        if attempt < max_attempts:
            time.sleep(RETRY_DELAY_SECONDS)

    from app.services.email_delivery_log import record_delivery

    record_delivery(
        kind=kind,
        to=recipient,
        subject=subject,
        provider=provider,
        ok=False,
        attempts=max_attempts,
        error=last_error,
    )
    return EmailDeliveryResult(
        ok=False,
        recipient=recipient,
        subject=subject,
        kind=kind,
        provider=provider,
        attempts=max_attempts,
        error=last_error,
    )
