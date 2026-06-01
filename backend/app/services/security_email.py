"""Correos de alertas de seguridad (bloqueo, contraseña, correo, accesos)."""
from __future__ import annotations

import logging

from app.core.config import settings
from app.services.email_dispatch import dispatch_notification_email

logger = logging.getLogger(__name__)


def _security_enabled() -> bool:
    return bool(getattr(settings, "security_email_alerts_enabled", True))


def dispatch_account_lockout_email(to_email: str, *, lockout_minutes: int) -> None:
    if not _security_enabled():
        return
    title = "Cuenta bloqueada temporalmente"
    message = (
        f"Tu cuenta en Ferragro fue bloqueada tras varios intentos fallidos de inicio de sesión. "
        f"Podrás volver a intentar en aproximadamente {lockout_minutes} minutos.\n\n"
        "Si no fuiste tú, cambia tu contraseña en cuanto recuperes el acceso o contacta a soporte."
    )
    dispatch_notification_email(to_email, title, message)


def dispatch_failed_login_warning_email(
    to_email: str,
    *,
    failures: int,
    max_attempts: int,
) -> None:
    if not _security_enabled():
        return
    remaining = max(0, max_attempts - failures)
    title = "Intentos fallidos de inicio de sesión"
    message = (
        f"Detectamos {failures} intento(s) fallido(s) de acceso a tu cuenta Ferragro. "
        f"Tras {max_attempts} intentos la cuenta se bloqueará temporalmente "
        f"(te quedan {remaining} intento(s) antes del bloqueo).\n\n"
        "Si no reconoces esta actividad, contacta a soporte de inmediato."
    )
    dispatch_notification_email(to_email, title, message)


def dispatch_password_changed_email(to_email: str) -> None:
    if not _security_enabled():
        return
    title = "Tu contraseña fue actualizada"
    message = (
        "Confirmamos que la contraseña de tu cuenta Ferragro se cambió correctamente.\n\n"
        "Si no realizaste este cambio, contacta a soporte de inmediato."
    )
    dispatch_notification_email(to_email, title, message)


def dispatch_email_address_changed_email(
    to_email: str,
    *,
    previous_email: str,
    new_email: str,
) -> None:
    if not _security_enabled():
        return
    title = "Correo de acceso actualizado"
    message = (
        "El correo asociado a tu cuenta Ferragro fue actualizado.\n\n"
        f"Anterior: {previous_email}\n"
        f"Nuevo: {new_email}\n\n"
        "Si no solicitaste este cambio, contacta a soporte de inmediato."
    )
    dispatch_notification_email(to_email, title, message)
    if previous_email.lower() != new_email.lower():
        dispatch_notification_email(
            previous_email,
            title,
            message,
        )


def dispatch_suspicious_login_email(
    to_email: str,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    if not _security_enabled():
        return
    ip_label = ip_address or "desconocida"
    ua_label = (user_agent or "desconocido")[:200]
    title = "Nuevo inicio de sesión detectado"
    message = (
        "Detectamos un inicio de sesión exitoso desde un dispositivo o red que no coincide "
        "con tus accesos recientes.\n\n"
        f"Dirección IP: {ip_label}\n"
        f"Navegador/dispositivo: {ua_label}\n\n"
        "Si fuiste tú, puedes ignorar este aviso. Si no, cambia tu contraseña y avisa a soporte."
    )
    dispatch_notification_email(to_email, title, message)
