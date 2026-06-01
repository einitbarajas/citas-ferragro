"""Redirección y candidatos de inbox en Resend sandbox."""
from __future__ import annotations

from app.core.config import settings
from app.services.email_utils import normalize_email


def resend_sandbox_inbox_candidates() -> list[str]:
    """
    Correos que Resend sandbox puede recibir (cuenta API + configuración explícita).
    Orden: RESEND_SANDBOX_INBOX → SMTP_USER (cuenta Resend) → admin bootstrap → from.
    """
    if not settings.resend_sandbox or not settings.resend_send_ready:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in (
        settings.resend_sandbox_inbox,
        settings.smtp_user,
        settings.admin_bootstrap_email,
        settings.smtp_from_email,
    ):
        inbox = normalize_email(str(candidate or "").strip())
        if not inbox:
            continue
        key = inbox.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(inbox)
    return ordered


def resend_sandbox_inbox() -> str | None:
    candidates = resend_sandbox_inbox_candidates()
    return candidates[0] if candidates else None


def redirect_recipient_for_sandbox(to_email: str, message: str) -> tuple[str, str]:
    """
    En sandbox, si el destinatario no es un inbox candidato, redirige al primero disponible.
    Si el destinatario ya es un inbox candidato, envía directo (evita romper recuperación Gmail).
    """
    delivery = normalize_email(to_email) or ""
    if not settings.resend_sandbox or not settings.resend_send_ready:
        return delivery, message
    if not delivery:
        return delivery, message

    candidates = resend_sandbox_inbox_candidates()
    if not candidates:
        return delivery, message

    delivery_lower = delivery.lower()
    if any(delivery_lower == c.lower() for c in candidates):
        return delivery, message

    inbox = candidates[0]
    note = f"[Modo prueba Resend — destinatario original: {delivery}]\n\n"
    return inbox, note + message


def sandbox_delivery_hint(original_to: str, actual_to: str) -> str | None:
    if not settings.resend_sandbox or actual_to.lower() == normalize_email(original_to or "").lower():
        return None
    return (
        f"En modo prueba el correo se envió a {actual_to} "
        f"(solicitado para {original_to}). Revisa esa bandeja."
    )
