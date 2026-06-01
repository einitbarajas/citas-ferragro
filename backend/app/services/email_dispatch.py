"""Envío de correos transaccionales en segundo plano (no bloquea la respuesta HTTP)."""
import atexit
import logging
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.services.email_utils import dedupe_emails, is_deliverable_email, normalize_email
from app.services.mailer import (
    send_internal_welcome_email,
    send_notification_email_with_retry,
    send_welcome_email,
)

logger = logging.getLogger(__name__)

_PROVIDER_ACTION_TITLES = {
    "updated": "Cuenta de proveedor actualizada",
    "suspended": "Cuenta de proveedor suspendida",
    "reactivated": "Cuenta de proveedor reactivada",
    "deleted": "Cuenta de proveedor eliminada",
    "purged": "Datos de proveedor purgados",
}

_email_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ferragro-email")


def shutdown_email_executor() -> None:
    _email_executor.shutdown(wait=False, cancel_futures=True)


atexit.register(shutdown_email_executor)


def _prepare_smtp_for_send() -> bool:
    from app.services.email_delivery import prepare_mail_transport

    return prepare_mail_transport()


def _run_in_email_pool(fn, *args, **kwargs) -> None:
    # En Render el hilo en background a veces no termina tras cerrar la petición HTTP.
    # En producción enviamos en el mismo hilo (como forgot-password) para no perder avisos.
    if settings.is_production:
        fn(*args, **kwargs)
        return
    _email_executor.submit(fn, *args, **kwargs)


def _resend_sandbox_inbox() -> str | None:
    """Resend sandbox solo entrega al correo de la cuenta; consolidamos avisos ahí."""
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


def _send_notification_email_blocking(to_email: str, title: str, message: str) -> None:
    try:
        from app.core.smtp_env_loader import overlay_render_smtp_secret

        if settings.is_production:
            overlay_render_smtp_secret()
        if not _prepare_smtp_for_send():
            logger.warning("SMTP no listo; aviso no enviado a %s | %s", to_email, title)
            return
        attempts = 3 if settings.is_production else 2
        if not send_notification_email_with_retry(
            to_email,
            title,
            message,
            max_attempts=attempts,
            force_secret_overlay=settings.is_production,
        ):
            logger.warning("Correo de aviso no enviado a %s | %s", to_email, title)
    except Exception:
        logger.exception("Error al enviar aviso a %s | %s", to_email, title)


def dispatch_notification_emails_batch(
    to_emails: list[str], *, title: str, message: str
) -> None:
    """
    Envía el mismo aviso a varios destinatarios.
    En Resend sandbox agrupa en un solo correo al inbox de prueba (Resend solo entrega ahí).
    """
    recipients = dedupe_emails(to_emails)
    if not recipients:
        logger.warning("Aviso sin destinatarios | %s", title)
        return
    sandbox_inbox = _resend_sandbox_inbox()
    if sandbox_inbox:
        body = (
            f"[Modo prueba Resend — este aviso iba a: {', '.join(recipients)}]\n\n{message}"
        )
        logger.info(
            "Sandbox: aviso '%s' consolidado a %s (%d destinatario(s))",
            title,
            sandbox_inbox,
            len(recipients),
        )
        dispatch_notification_email(sandbox_inbox, title, body)
        return
    for to_email in recipients:
        dispatch_notification_email(to_email, title, message)


def _send_welcome_provider_blocking(to_email: str, recipient_name: str) -> None:
    try:
        if not _prepare_smtp_for_send():
            logger.warning("SMTP no listo; bienvenida proveedor no enviada a %s", to_email)
            return
        if not send_welcome_email(to_email, recipient_name):
            logger.warning("Correo de bienvenida (proveedor) no enviado a %s", to_email)
    except Exception:
        logger.exception("Error al enviar bienvenida de proveedor a %s", to_email)


def _send_welcome_staff_blocking(to_email: str, recipient_name: str, role_name: str) -> None:
    try:
        if not _prepare_smtp_for_send():
            logger.warning("SMTP no listo; bienvenida staff no enviada a %s", to_email)
            return
        if not send_internal_welcome_email(to_email, recipient_name, role_name):
            logger.warning("Correo de bienvenida (staff) no enviado a %s", to_email)
    except Exception:
        logger.exception("Error al enviar bienvenida de usuario interno a %s", to_email)


def _normalize_recipient(to_email: str) -> str | None:
    email = normalize_email(to_email)
    if not email or not is_deliverable_email(email):
        return None
    return email


def dispatch_welcome_provider(to_email: str, recipient_name: str) -> None:
    normalized = _normalize_recipient(to_email)
    if not normalized:
        return
    _run_in_email_pool(_send_welcome_provider_blocking, normalized, recipient_name)


def dispatch_welcome_staff(to_email: str, recipient_name: str, role_name: str) -> None:
    normalized = _normalize_recipient(to_email)
    if not normalized:
        return
    _run_in_email_pool(_send_welcome_staff_blocking, normalized, recipient_name, role_name)


def send_recovery_password_email(account_email: str, temporary_password: str) -> bool:
    """Envío de recuperación (síncrono en Render; usa Resend/Brevo si SMTP está bloqueado)."""
    normalized = _normalize_recipient(account_email)
    if not normalized:
        logger.warning("Recuperación omitida (correo inválido): %r", account_email)
        return False
    try:
        from app.core.config import refresh_smtp_settings
        from app.core.smtp_env_loader import overlay_render_smtp_secret
        from app.services.email_transport import email_delivery_ready
        from app.services.mailer import send_temporary_password_email_with_retry

        overlay_render_smtp_secret()
        refresh_smtp_settings()
        if not email_delivery_ready() and not settings.smtp_send_ready:
            logger.warning(
                "Correo no listo; recuperación no enviada a %s (clave en BD/logs SMTP_RECOVERY)",
                normalized,
            )
            return False
        attempts = 3 if settings.is_production else 2
        sent = send_temporary_password_email_with_retry(
            normalized,
            temporary_password,
            account_email=normalized,
            attempts=attempts,
            force_secret_overlay=settings.is_production,
        )
        if not sent:
            logger.warning(
                "SMTP_RECOVERY correo=%s clave_temporal=%s (correo no enviado)",
                normalized,
                temporary_password,
            )
        return bool(sent)
    except Exception:
        logger.exception("SMTP_RECOVERY fallo al enviar a %s", normalized)
        logger.warning(
            "SMTP_RECOVERY correo=%s clave_temporal=%s",
            normalized,
            temporary_password,
        )
        return False


def send_recovery_password_email_background(account_email: str, temporary_password: str) -> None:
    """Alias para tareas en segundo plano (dev)."""
    send_recovery_password_email(account_email, temporary_password)


def dispatch_notification_email(to_email: str, title: str, message: str) -> None:
    normalized = _normalize_recipient(to_email)
    if not normalized:
        logger.warning("Correo de aviso omitido (destinatario inválido): %r | %s", to_email, title)
        return
    _run_in_email_pool(_send_notification_email_blocking, normalized, title, message)


def dispatch_provider_account_notice(
    *,
    provider_email: str,
    provider_name: str,
    admin_emails: list[str],
    action: str,
    detail: str,
    actor_label: str,
) -> None:
    admins = dedupe_emails(admin_emails)
    logger.info(
        "Aviso cuenta proveedor action=%s | proveedor=%s | admins=%s",
        action,
        provider_email,
        admins,
    )
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
    provider_key = (normalize_email(provider_email) or "").lower()
    for admin_email in admins:
        key = admin_email.lower()
        if key in seen:
            continue
        seen.add(key)
        if provider_key and key == provider_key:
            continue
        dispatch_notification_email(admin_email, admin_title, admin_body)
