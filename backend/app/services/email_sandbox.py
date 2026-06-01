"""Redirección de destinatarios en Resend sandbox (solo entrega al inbox de la cuenta)."""
from __future__ import annotations

from app.core.config import settings
from app.services.email_utils import normalize_email


def resend_sandbox_inbox() -> str | None:
    if not settings.resend_sandbox or not settings.resend_send_ready:
        return None
    for candidate in (
        settings.resend_sandbox_inbox,
        settings.admin_bootstrap_email,
        settings.smtp_from_email,
        settings.smtp_user,
    ):
        inbox = normalize_email(str(candidate or "").strip())
        if inbox:
            return inbox
    return None


def redirect_recipient_for_sandbox(to_email: str, message: str) -> tuple[str, str]:
    """Si sandbox, envía al inbox permitido y deja constancia del destinatario original."""
    delivery = normalize_email(to_email) or ""
    inbox = resend_sandbox_inbox()
    if not inbox or not delivery or delivery.lower() == inbox.lower():
        return delivery, message
    note = f"[Destinatario original: {delivery}]\n\n"
    return inbox, note + message
