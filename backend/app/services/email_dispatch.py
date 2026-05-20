"""Envío de correos transaccionales sin bloquear la operación principal."""
import logging

from app.services.mailer import send_internal_welcome_email, send_notification_email, send_welcome_email

logger = logging.getLogger(__name__)

_PROVIDER_ACTION_TITLES = {
    "updated": "Cuenta de proveedor actualizada",
    "suspended": "Cuenta de proveedor suspendida",
    "reactivated": "Cuenta de proveedor reactivada",
    "deleted": "Cuenta de proveedor eliminada",
    "purged": "Datos de proveedor purgados",
}


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


def dispatch_provider_account_notice(
    *,
    provider_email: str,
    provider_name: str,
    admin_emails: list[str],
    action: str,
    detail: str,
    actor_label: str,
) -> None:
    title = _PROVIDER_ACTION_TITLES.get(action, "Aviso de cuenta proveedor")
    provider_body = (
        f"Hola {provider_name},\n\n"
        f"{detail}\n\n"
        f"Acción registrada por: {actor_label}.\n\n"
        "Si no reconoces este cambio, contacta a soporte Ferragro."
    )
    dispatch_notification_email(provider_email, title, provider_body)

    admin_title = f"[Admin] {title} — {provider_name}"
    admin_body = (
        f"Proveedor: {provider_name}\n"
        f"Correo: {provider_email}\n\n"
        f"{detail}\n\n"
        f"Realizado por: {actor_label}."
    )
    seen: set[str] = set()
    for admin_email in admin_emails:
        key = admin_email.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        if key == provider_email.strip().lower():
            continue
        dispatch_notification_email(admin_email, admin_title, admin_body)
