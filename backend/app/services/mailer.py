"""Utilidad simple de correo SMTP (fallback a logs si no hay SMTP_HOST)."""
import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from contextlib import contextmanager
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from app.core.config import refresh_smtp_settings, settings
from app.services.email_utils import is_deliverable_email, normalize_email

logger = logging.getLogger(__name__)


def _smtp_delivery_attempts() -> list[tuple[str, object]]:
    host = (settings.smtp_host or "").lower()
    if "gmail.com" not in host:
        return [("primary", lambda: _smtp_client())]

    attempts: list[tuple[str, object]] = []
    seen: set[str] = set()

    def _add(label: str, factory) -> None:
        if label in seen:
            return
        seen.add(label)
        attempts.append((label, factory))

    # Usar primero el perfil que smtp_resolver ya validó (evita 465 fallido + timeout en 587).
    if settings.smtp_use_ssl:
        _add("current_ssl", lambda: _smtp_client())
    else:
        _add("current_starttls", lambda: _smtp_client())
    _add(
        "gmail_ssl_465",
        lambda: _smtp_client(use_ssl=True, port=465, use_tls=False),
    )
    _add(
        "gmail_starttls_587",
        lambda: _smtp_client(use_ssl=False, port=587, use_tls=True),
    )
    return attempts


def _refresh_smtp_for_delivery() -> bool:
    """Mantiene el perfil SMTP activo; en Render prioriza smtp.env sobre env sueltas."""
    if settings.is_production:
        from app.core.smtp_env_loader import overlay_render_smtp_secret
        from app.services.smtp_resolver import ensure_smtp_login_ready, resolved_smtp_label

        overlay_render_smtp_secret()
        refresh_smtp_settings()
        if resolved_smtp_label():
            return settings.smtp_send_ready
        return ensure_smtp_login_ready()
    refresh_smtp_settings()
    return settings.smtp_send_ready


def smtp_login_probe() -> bool:
    """Prueba login SMTP (mismos intentos que el envío real)."""
    if settings.is_production:
        from app.services.smtp_resolver import ensure_smtp_login_ready

        return ensure_smtp_login_ready()
    refresh_smtp_settings()
    if not settings.smtp_send_ready:
        return False
    for label, client_factory in _smtp_delivery_attempts():
        try:
            with client_factory():
                return True
        except Exception as exc:
            logger.warning("SMTP login probe %s falló: %s", label, exc)
    logger.error(
        "SMTP login probe falló (host=%s user=%s from=%s)",
        settings.smtp_host,
        settings.smtp_user,
        settings.smtp_from_email,
    )
    return False


def smtp_login_probe_with_timeout(timeout_seconds: float = 18.0) -> bool | None:
    """Probe SMTP con límite de tiempo (evita página en blanco en /health/deep)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(smtp_login_probe)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            logger.warning("SMTP login probe excedió %ss", timeout_seconds)
            return None


SUPPORT_EMAIL = "ecommerce@ferragro.com"
SUPPORT_PHONE = "+57 3142254819"
SUPPORT_WHATSAPP_URL = "https://wa.me/573142254819"
COMPANY_ADDRESS = "Carrera 41 #46-167, Itagui-Ant"
COMPANY_WEBSITE = "https://www.ferragro.com"
_LOGO_CANDIDATES = (
    Path(__file__).resolve().parents[2] / "static" / "ferragro-blan-bord.png",
    Path(__file__).resolve().parents[3] / "frontend" / "public" / "ferragro-blan-bord.png",
)
LOGO_PATH = next((p for p in _LOGO_CANDIDATES if p.is_file()), _LOGO_CANDIDATES[0])
LOGO_CID = "ferragro-logo-watermark"
SMTP_TIMEOUT_SECONDS = 8


def _smtp_envelope_from() -> str:
    return normalize_email(settings.smtp_from_email) or normalize_email(settings.smtp_user) or ""


@contextmanager
def _smtp_client(*, use_ssl: bool | None = None, port: int | None = None, use_tls: bool | None = None):
    """Conexión STARTTLS (587) o SSL directo (465), según configuración."""
    ssl_mode = settings.smtp_use_ssl if use_ssl is None else use_ssl
    smtp_port = settings.smtp_port if port is None else port
    tls_mode = settings.smtp_use_tls if use_tls is None else use_tls

    if ssl_mode:
        client = smtplib.SMTP_SSL(settings.smtp_host, smtp_port, timeout=SMTP_TIMEOUT_SECONDS)
        try:
            client.ehlo()
            if settings.smtp_user:
                client.login(settings.smtp_user, settings.smtp_password)
            yield client
        finally:
            client.quit()
        return

    client = smtplib.SMTP(settings.smtp_host, smtp_port, timeout=SMTP_TIMEOUT_SECONDS)
    try:
        client.ehlo()
        if tls_mode:
            client.starttls()
            client.ehlo()
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        yield client
    finally:
        client.quit()


def _deliver_smtp_message(message: MIMEMultipart, delivery: str) -> None:
    from_addr = _smtp_envelope_from()
    if not from_addr:
        raise ValueError("SMTP sin remitente (SMTP_FROM_EMAIL / SMTP_USER)")

    if settings.is_production:
        from app.services.smtp_resolver import ensure_smtp_login_ready, resolved_smtp_label

        if not resolved_smtp_label() and not ensure_smtp_login_ready():
            raise smtplib.SMTPAuthenticationError(
                535,
                b"Gmail no acepto login desde Render; revisa smtp.env y contrasena de aplicacion",
            )

    payload = message.as_string()
    last_error: Exception | None = None
    for label, client_factory in _smtp_delivery_attempts():
        try:
            with client_factory() as client:
                client.sendmail(from_addr, [delivery], payload)
            if label != "primary":
                logger.info("Correo enviado con fallback SMTP %s", label)
            return
        except Exception as exc:
            last_error = exc
            logger.warning("SMTP intento %s falló para %s: %s", label, delivery, exc)
    if last_error is not None:
        raise last_error


def _reply_to_address() -> str:
    explicit = normalize_email(settings.smtp_reply_to)
    if explicit:
        return explicit
    from_addr = normalize_email(settings.smtp_from_email)
    return from_addr or SUPPORT_EMAIL


def _build_mail_layout(body_html: str) -> str:
    logo_html = (
        f'<img src="cid:{LOGO_CID}" alt="Ferragro" '
        "style=\"width:260px;max-width:100%;height:auto;display:block;margin:0 auto;\" />"
    )
    if not LOGO_PATH.exists():
        logo_html = (
            "<div style=\"font-size:32px;font-weight:800;letter-spacing:2px;"
            "color:#0f6e2f;text-align:center;\">FERRAGRO</div>"
        )

    return f"""\
<!DOCTYPE html>
<html lang="es">
  <body style="margin:0;padding:0;background:#f3f7f4;font-family:Arial,sans-serif;color:#1f2937;">
    <div style="max-width:640px;margin:24px auto;padding:0 12px;">
      <div style="overflow:hidden;border:1px solid #dbe9dd;border-radius:14px;background:#ffffff;">
        <div style="padding:18px 20px 0;">
          {logo_html}
        </div>
        <div style="padding:20px 28px 30px;">
          {body_html}
          <div style="margin-top:18px;padding-top:14px;border-top:1px solid #dbe9dd;">
            <p style="margin:0 0 6px;line-height:1.5;font-size:14px;">
              <strong>Soporte:</strong>
              <a href="mailto:{SUPPORT_EMAIL}" style="color:#0f6e2f;text-decoration:none;">{SUPPORT_EMAIL}</a>
            </p>
            <p style="margin:0 0 6px;line-height:1.5;font-size:14px;">
              <strong>WhatsApp:</strong>
              <a href="{SUPPORT_WHATSAPP_URL}" style="color:#0f6e2f;text-decoration:none;">{SUPPORT_PHONE}</a>
            </p>
            <p style="margin:0 0 6px;line-height:1.5;font-size:14px;">
              <strong>Dirección:</strong> {COMPANY_ADDRESS}
            </p>
            <p style="margin:0;line-height:1.5;font-size:14px;">
              <strong>Sitio web:</strong>
              <a href="{COMPANY_WEBSITE}" style="color:#0f6e2f;text-decoration:none;">{COMPANY_WEBSITE}</a>
            </p>
          </div>
          <p style="margin:20px 0 0;color:#0f6e2f;font-weight:700;">Ferragro</p>
        </div>
      </div>
    </div>
  </body>
</html>
"""


def send_branded_email(subject: str, to_email: str, plain_body: str, content_html: str) -> bool:
    delivery = normalize_email(to_email)
    if not delivery or not is_deliverable_email(delivery):
        logger.warning("Correo no enviado (destinatario inválido): %r subject=%s", to_email, subject)
        return False

    html_body = _build_mail_layout(content_html)

    if settings.resend_send_ready:
        from app.services.resend_mailer import send_resend_email

        return send_resend_email(
            to_email=delivery,
            subject=subject,
            plain_body=plain_body,
            html_body=html_body,
        )

    if not _refresh_smtp_for_delivery():
        logger.warning(
            "Correo no enviado (SMTP incompleto: host/from/user/password). to=%s subject=%s",
            delivery,
            subject,
        )
        return False

    from_addr = _smtp_envelope_from() or settings.smtp_from_email
    message = MIMEMultipart("related")
    message["Subject"] = subject
    message["From"] = formataddr((settings.smtp_from_name, from_addr))
    message["To"] = delivery
    message["Reply-To"] = _reply_to_address()
    alternative_part = MIMEMultipart("alternative")
    alternative_part.attach(MIMEText(plain_body, "plain", _charset="utf-8"))
    alternative_part.attach(MIMEText(html_body, "html", _charset="utf-8"))
    message.attach(alternative_part)
    if LOGO_PATH.exists():
        with LOGO_PATH.open("rb") as image_file:
            logo_mime = MIMEImage(image_file.read(), _subtype="png")
        logo_mime.add_header("Content-ID", f"<{LOGO_CID}>")
        logo_mime.add_header("Content-Disposition", "inline", filename="ferragro-blan-bord.png")
        message.attach(logo_mime)

    try:
        _deliver_smtp_message(message, delivery)
        return True
    except smtplib.SMTPAuthenticationError as exc:
        logger.error(
            "SMTP autenticación fallida (host=%s user=%s): %s",
            settings.smtp_host,
            settings.smtp_user,
            exc,
        )
        raise
    except smtplib.SMTPException as exc:
        logger.error("SMTP error al enviar a %s: %s", delivery, exc)
        raise


def send_temporary_password_email(
    to_email: str,
    temporary_password: str,
    *,
    account_email: str | None = None,
) -> bool:
    delivery = str(account_email or to_email).strip()

    subject = "Ferragro - Contraseña temporal"
    plain_body = (
        "Hola,\n\n"
        "Recibimos una solicitud para recuperar tu contraseña en Ferragro.\n\n"
        f"Tu contraseña temporal es: {temporary_password}\n\n"
        "Por seguridad, en el primer ingreso deberás cambiarla inmediatamente.\n"
        "Si no solicitaste este cambio, contacta al equipo de soporte.\n\n"
        f"Soporte: {SUPPORT_EMAIL} | WhatsApp: {SUPPORT_PHONE}\n"
        f"Direccion: {COMPANY_ADDRESS}\n"
        f"Sitio web: {COMPANY_WEBSITE}\n\n"
        "Ferragro"
    )
    content_html = f"""
          <h1 style="margin:0 0 16px;font-size:22px;color:#0f6e2f;">Recuperación de contraseña</h1>
          <p style="margin:0 0 14px;line-height:1.6;">Hola,</p>
          <p style="margin:0 0 14px;line-height:1.6;">
            Recibimos una solicitud para recuperar tu contraseña en Ferragro.
          </p>
          <p style="margin:0 0 8px;line-height:1.6;">Tu contraseña temporal es:</p>
          <p style="margin:0 0 18px;">
            <span style="display:inline-block;padding:10px 14px;border:1px dashed #0f6e2f;border-radius:8px;background:#f6fff7;font-size:20px;font-weight:700;letter-spacing:1px;color:#0f6e2f;">
              {temporary_password}
            </span>
          </p>
          <p style="margin:0 0 10px;line-height:1.6;">
            Por seguridad, en el primer ingreso deberás cambiarla inmediatamente.
          </p>
          <p style="margin:0;line-height:1.6;">
            Si no solicitaste este cambio, contacta al equipo de soporte.
          </p>
"""
    return send_branded_email(subject, delivery, plain_body, content_html)


def send_temporary_password_email_with_retry(
    to_email: str,
    temporary_password: str,
    *,
    account_email: str | None = None,
    attempts: int = 2,
    force_secret_overlay: bool = False,
) -> bool:
    """Recuperación de contraseña: re-lee SMTP y reintenta (Render)."""
    for attempt in range(1, max(1, attempts) + 1):
        if settings.is_production:
            if not _refresh_smtp_for_delivery():
                logger.warning("SMTP no listo para recuperación (intento %s)", attempt)
                continue
        else:
            refresh_smtp_settings(force_secret_overlay=force_secret_overlay)
        if not settings.smtp_send_ready:
            logger.warning("SMTP no listo para recuperación (intento %s)", attempt)
            continue
        try:
            if send_temporary_password_email(
                to_email,
                temporary_password,
                account_email=account_email,
            ):
                return True
        except Exception:
            logger.exception("Recuperación SMTP intento %s falló para %s", attempt, to_email)
    return False


def send_welcome_email(to_email: str, recipient_name: str) -> bool:
    subject = "Ferragro - Bienvenido(a)"
    display_name = (recipient_name or "").strip() or "proveedor(a)"
    plain_body = (
        f"Hola {display_name},\n\n"
        "Te damos la bienvenida a Ferragro.\n"
        "Tu registro fue creado correctamente y ya puedes ingresar a la plataforma para gestionar tus citas de entrega.\n\n"
        "Si tienes dudas, nuestro equipo de soporte está disponible para ayudarte.\n\n"
        f"Soporte: {SUPPORT_EMAIL} | WhatsApp: {SUPPORT_PHONE}\n"
        f"Direccion: {COMPANY_ADDRESS}\n"
        f"Sitio web: {COMPANY_WEBSITE}\n\n"
        "Ferragro"
    )
    content_html = f"""
          <h1 style="margin:0 0 16px;font-size:22px;color:#0f6e2f;">¡Bienvenido(a) a Ferragro!</h1>
          <p style="margin:0 0 14px;line-height:1.6;">Hola <strong>{display_name}</strong>,</p>
          <p style="margin:0 0 14px;line-height:1.6;">
            Tu registro fue creado correctamente y ya puedes ingresar a la plataforma para gestionar tus citas de entrega.
          </p>
          <p style="margin:0;line-height:1.6;">
            Si tienes dudas, nuestro equipo de soporte está disponible para ayudarte.
          </p>
"""
    return send_branded_email(subject, to_email, plain_body, content_html)


def send_internal_welcome_email(to_email: str, recipient_name: str, role_name: str) -> bool:
    subject = "Ferragro - Cuenta de usuario creada"
    display_name = (recipient_name or "").strip() or "usuario(a)"
    role_label = (role_name or "").strip() or "usuario interno"
    plain_body = (
        f"Hola {display_name},\n\n"
        "Te damos la bienvenida a Ferragro.\n"
        f"Se creó tu cuenta con rol {role_label}. Ya puedes ingresar al panel con tu correo "
        "y la contraseña que te indicó el administrador.\n\n"
        "Si tienes dudas, nuestro equipo de soporte está disponible para ayudarte.\n\n"
        f"Soporte: {SUPPORT_EMAIL} | WhatsApp: {SUPPORT_PHONE}\n"
        f"Direccion: {COMPANY_ADDRESS}\n"
        f"Sitio web: {COMPANY_WEBSITE}\n\n"
        "Ferragro"
    )
    content_html = f"""
          <h1 style="margin:0 0 16px;font-size:22px;color:#0f6e2f;">¡Bienvenido(a) a Ferragro!</h1>
          <p style="margin:0 0 14px;line-height:1.6;">Hola <strong>{display_name}</strong>,</p>
          <p style="margin:0 0 14px;line-height:1.6;">
            Se creó tu cuenta con rol <strong>{role_label}</strong>. Ya puedes ingresar al panel con tu correo
            y la contraseña que te indicó el administrador.
          </p>
          <p style="margin:0;line-height:1.6;">
            Si tienes dudas, nuestro equipo de soporte está disponible para ayudarte.
          </p>
"""
    return send_branded_email(subject, to_email, plain_body, content_html)


def send_notification_email(to_email: str, title: str, message: str) -> bool:
    subject = f"Ferragro - {title}"
    plain_body = (
        f"{title}\n\n"
        f"{message}\n\n"
        "Ingresa al panel de Ferragro para ver el detalle.\n\n"
        f"Soporte: {SUPPORT_EMAIL} | WhatsApp: {SUPPORT_PHONE}\n"
        f"Direccion: {COMPANY_ADDRESS}\n"
        f"Sitio web: {COMPANY_WEBSITE}\n\n"
        "Ferragro"
    )
    safe_title = title.replace("<", "&lt;").replace(">", "&gt;")
    safe_message = message.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br />")
    content_html = f"""
          <h1 style="margin:0 0 16px;font-size:22px;color:#0f6e2f;">{safe_title}</h1>
          <p style="margin:0;line-height:1.6;">{safe_message}</p>
          <p style="margin:18px 0 0;line-height:1.6;">
            Ingresa al panel de Ferragro para ver el detalle.
          </p>
"""
    return send_branded_email(subject, to_email, plain_body, content_html)
