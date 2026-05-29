"""Detección de correo en producción (Render free bloquea SMTP 587/465)."""
from __future__ import annotations

import logging
import smtplib

from app.core.config import settings

logger = logging.getLogger(__name__)

_render_smtp_blocked: bool | None = None


def render_smtp_blocked() -> bool:
    """True si Gmail SMTP no responde (típico en Render free)."""
    global _render_smtp_blocked
    if _render_smtp_blocked is not None:
        return _render_smtp_blocked
    if not settings.is_production or not settings.smtp_send_ready:
        _render_smtp_blocked = False
        return False
    if settings.resend_send_ready or settings.brevo_send_ready:
        _render_smtp_blocked = True
        return True
    host = settings.smtp_host
    port = settings.smtp_port or 587
    try:
        client = smtplib.SMTP(host, port, timeout=4)
        client.ehlo()
        client.starttls()
        client.ehlo()
        client.login(settings.smtp_user, settings.smtp_password)
        client.quit()
        _render_smtp_blocked = False
    except Exception as exc:
        logger.warning("SMTP directo no disponible en este host (%s): %s", host, exc)
        _render_smtp_blocked = True
    return _render_smtp_blocked


def production_should_use_https_email() -> bool:
    if not settings.is_production:
        return False
    if settings.resend_send_ready or settings.brevo_send_ready:
        return True
    return render_smtp_blocked()


def email_delivery_ready() -> bool:
    if production_should_use_https_email():
        return settings.resend_send_ready or settings.brevo_send_ready
    return settings.smtp_send_ready or settings.resend_send_ready or settings.brevo_send_ready
