"""Envío de correos transaccionales sin bloquear la operación principal."""
import logging

from app.services.mailer import send_internal_welcome_email, send_notification_email, send_welcome_email

logger = logging.getLogger(__name__)


def dispatch_welcome_provider(to_email: str, recipient_name: str) -> None:
    normalized = str(to_email or "").strip()
    if not normalized:
        return
    try:
        if not send_welcome_email(normalized, recipient_name):
            logger.warning("Correo de bienvenida (proveedor) no enviado a %s", normalized)
    except Exception:
        logger.exception("Error al enviar bienvenida de proveedor a %s", normalized)


def dispatch_welcome_staff(to_email: str, recipient_name: str, role_name: str) -> None:
    normalized = str(to_email or "").strip()
    if not normalized:
        return
    try:
        if not send_internal_welcome_email(normalized, recipient_name, role_name):
            logger.warning("Correo de bienvenida (staff) no enviado a %s", normalized)
    except Exception:
        logger.exception("Error al enviar bienvenida de usuario interno a %s", normalized)


def dispatch_notification_email(to_email: str, title: str, message: str) -> None:
    normalized = str(to_email or "").strip()
    if not normalized:
        return
    try:
        if not send_notification_email(normalized, title, message):
            logger.warning("Correo de aviso no enviado a %s | %s", normalized, title)
    except Exception:
        logger.exception("Error al enviar aviso a %s | %s", normalized, title)
