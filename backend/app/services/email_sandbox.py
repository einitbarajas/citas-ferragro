"""Redirección y candidatos de inbox en Resend sandbox."""
from __future__ import annotations

import os

from app.core.config import settings
from app.services.email_utils import normalize_email


def _configured_sandbox_inbox() -> str:
    """Lee inbox sin depender solo del modelo Settings (compatible con deploys viejos)."""
    for raw in (
        os.getenv("RESEND_SANDBOX_INBOX", ""),
        str(getattr(settings, "resend_sandbox_inbox", "") or ""),
        settings.smtp_user,
        settings.admin_bootstrap_email,
        settings.smtp_from_email,
    ):
        inbox = normalize_email(str(raw or "").strip())
        if inbox:
            return inbox
    return ""


def resend_sandbox_inbox_candidates() -> list[str]:
    if not settings.resend_sandbox or not settings.resend_send_ready:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in (
        os.getenv("RESEND_SANDBOX_INBOX", ""),
        str(getattr(settings, "resend_sandbox_inbox", "") or ""),
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
    try:
        candidates = resend_sandbox_inbox_candidates()
        return candidates[0] if candidates else None
    except Exception:
        inbox = _configured_sandbox_inbox()
        return inbox or None


def redirect_recipient_for_sandbox(to_email: str, message: str) -> tuple[str, str]:
    delivery = normalize_email(to_email) or ""
    if not settings.resend_sandbox or not settings.resend_send_ready:
        return delivery, message
    if not delivery:
        return delivery, message

    try:
        candidates = resend_sandbox_inbox_candidates()
    except Exception:
        candidates = []
    inbox = candidates[0] if candidates else _configured_sandbox_inbox()
    if not inbox:
        return delivery, message

    if delivery.lower() == inbox.lower():
        return delivery, message

    note = f"[Modo prueba Resend — destinatario original: {delivery}]\n\n"
    return inbox, note + message


def sandbox_delivery_hint(original_to: str, actual_to: str) -> str | None:
    if not settings.resend_sandbox or actual_to.lower() == normalize_email(original_to or "").lower():
        return None
    return (
        f"En modo prueba el correo se envió a {actual_to} "
        f"(solicitado para {original_to}). Revisa esa bandeja."
    )
