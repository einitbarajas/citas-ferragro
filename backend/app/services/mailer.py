"""Utilidad simple de correo SMTP (fallback a logs si no hay SMTP_HOST)."""
import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from contextlib import contextmanager
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
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
    """Mantiene el perfil SMTP activo; en Render prioriza smtp.env y Resend/Brevo (HTTPS)."""
    if settings.is_production:
        from app.core.smtp_env_loader import overlay_render_smtp_secret
        from app.services.email_transport import email_delivery_ready
        from app.services.smtp_resolver import ensure_smtp_login_ready, resolved_smtp_label

        overlay_render_smtp_secret()
        refresh_smtp_settings()
        if settings.resend_send_ready or settings.brevo_send_ready:
            return True
        if email_delivery_ready():
            return True
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
DEFAULT_PANEL_URL = "https://citas.ferragro.vercel.app"


def panel_url() -> str:
    url = (settings.public_panel_url or "").strip().rstrip("/")
    return url or DEFAULT_PANEL_URL


def panel_cta_plain() -> str:
    return f"Accede al panel: {panel_url()}\n"


def panel_cta_html(button_label: str = "Ir al panel Ferragro") -> str:
    url = panel_url()
    safe_label = button_label.replace("<", "&lt;").replace(">", "&gt;")
    return f"""
          <p style="margin:20px 0 0;text-align:center;">
            <a href="{url}"
               style="display:inline-block;padding:12px 22px;border-radius:8px;background:#35783C;color:#ffffff;
                      font-weight:700;text-decoration:none;font-size:15px;">
              {safe_label}
            </a>
          </p>
"""
from app.services.email_branding import LOGO_CID, LOGO_FILENAME, read_logo_bytes
from app.services.email_branding import logo_img_html as branding_logo_img_html

SMTP_TIMEOUT_SECONDS = 8


def public_logo_url() -> str:
    """URL absoluta del logo en correos HTTPS."""
    from app.services.email_branding import hosted_logo_url

    return hosted_logo_url()


def prefer_smtp_for_real_delivery() -> bool:
    """
    En desarrollo (o si SMTP funciona en producción), usar SMTP para que el correo
    llegue al destinatario real. Resend sandbox solo entrega a la cuenta Resend.
    """
    if not settings.smtp_send_ready:
        return False
    if not settings.is_production:
        return True
    from app.services.email_transport import production_should_use_https_email, render_smtp_blocked

    if settings.resend_sandbox and not render_smtp_blocked():
        return True
    return not production_should_use_https_email()


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


def _build_mail_layout(body_html: str, *, use_cid_logo: bool = True) -> str:
    logo_html = branding_logo_img_html(use_cid=use_cid_logo)

    return f"""\
<!DOCTYPE html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="color-scheme" content="light dark" />
    <meta name="supported-color-schemes" content="light dark" />
    <style type="text/css">
      @media (prefers-color-scheme: dark) {{
        .ferragro-email-card {{ background-color:#2d2d2d !important; border-color:#444444 !important; }}
        .ferragro-email-body {{ background-color:#1a1a1a !important; color:#e8eaed !important; }}
        .ferragro-email-footer {{ border-color:#444444 !important; }}
        .ferragro-email-link {{ color:#81c995 !important; }}
        .ferragro-email-brand {{ color:#81c995 !important; }}
      }}
    </style>
  </head>
  <body class="ferragro-email-body" style="margin:0;padding:0;background:#f3f7f4;font-family:Arial,sans-serif;color:#1f2937;">
    <div style="max-width:640px;margin:24px auto;padding:0 12px;">
      <div class="ferragro-email-card" style="overflow:hidden;border:1px solid #dbe9dd;border-radius:14px;background:#ffffff;">
        <div style="padding:18px 20px 0;background:transparent;">
          {logo_html}
        </div>
        <div style="padding:20px 28px 30px;">
          {body_html}
          <div class="ferragro-email-footer" style="margin-top:18px;padding-top:14px;border-top:1px solid #dbe9dd;">
            <p style="margin:0 0 6px;line-height:1.5;font-size:14px;">
              <strong>Soporte:</strong>
              <a class="ferragro-email-link" href="mailto:{SUPPORT_EMAIL}" style="color:#0f6e2f;text-decoration:none;">{SUPPORT_EMAIL}</a>
            </p>
            <p style="margin:0 0 6px;line-height:1.5;font-size:14px;">
              <strong>WhatsApp:</strong>
              <a class="ferragro-email-link" href="{SUPPORT_WHATSAPP_URL}" style="color:#0f6e2f;text-decoration:none;">{SUPPORT_PHONE}</a>
            </p>
            <p style="margin:0 0 6px;line-height:1.5;font-size:14px;">
              <strong>Dirección:</strong> {COMPANY_ADDRESS}
            </p>
            <p style="margin:0;line-height:1.5;font-size:14px;">
              <strong>Sitio web:</strong>
              <a class="ferragro-email-link" href="{COMPANY_WEBSITE}" style="color:#0f6e2f;text-decoration:none;">{COMPANY_WEBSITE}</a>
            </p>
          </div>
          <p class="ferragro-email-brand" style="margin:20px 0 0;color:#0f6e2f;font-weight:700;">Ferragro</p>
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

    use_smtp = prefer_smtp_for_real_delivery()
    using_resend = bool(
        not use_smtp
        and settings.resend_send_ready
        and not settings.brevo_send_ready
    )
    # Resend requiere adjunto inline + cid:; las URLs externas a veces las bloquea Gmail.
    html_body = _build_mail_layout(content_html, use_cid_logo=(use_smtp or using_resend))

    from app.services.email_transport import production_should_use_https_email

    if not use_smtp and (production_should_use_https_email() or settings.brevo_send_ready):
        if settings.brevo_send_ready:
            from app.services.brevo_mailer import send_brevo_email

            return send_brevo_email(
                to_email=delivery,
                subject=subject,
                plain_body=plain_body,
                html_body=html_body,
            )
        if settings.resend_send_ready:
            from app.services.resend_mailer import send_resend_email

            return send_resend_email(
                to_email=delivery,
                subject=subject,
                plain_body=plain_body,
                html_body=html_body,
            )
        logger.error(
            "Render bloquea SMTP; falta RESEND_API_KEY o BREVO_API_KEY en Environment/smtp.env"
        )
        return False

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
    logo_bytes = read_logo_bytes()
    if logo_bytes:
        logo_mime = MIMEImage(logo_bytes, _subtype="png")
        logo_mime.add_header("Content-ID", f"<{LOGO_CID}>")
        logo_mime.add_header("Content-Disposition", "inline", filename=LOGO_FILENAME)
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
        f"{panel_cta_plain()}"
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
          {panel_cta_html("Iniciar sesión en Ferragro")}
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
    """Recuperación de contraseña: re-lee secretos y reintenta (Render + Resend/Brevo)."""
    if force_secret_overlay and settings.is_production:
        from app.core.smtp_env_loader import overlay_render_smtp_secret

        overlay_render_smtp_secret()
    if not settings.is_production:
        refresh_smtp_settings(force_secret_overlay=force_secret_overlay)

    from app.services.email_delivery import deliver_with_retry

    delivery = str(account_email or to_email).strip()
    result = deliver_with_retry(
        lambda: send_temporary_password_email(
            to_email,
            temporary_password,
            account_email=account_email,
        ),
        recipient=delivery,
        subject="Ferragro - Contraseña temporal",
        kind="password_recovery",
        max_attempts=attempts,
    )
    return result.ok


def send_welcome_email(to_email: str, recipient_name: str) -> bool:
    subject = "Ferragro - Bienvenido(a)"
    display_name = (recipient_name or "").strip() or "proveedor(a)"
    plain_body = (
        f"Hola {display_name},\n\n"
        "Te damos la bienvenida a Ferragro.\n"
        "Tu registro fue creado correctamente y ya puedes ingresar a la plataforma para gestionar tus citas de entrega.\n"
        f"{panel_cta_plain()}"
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
          {panel_cta_html("Ingresar al panel")}
          <p style="margin:14px 0 0;line-height:1.6;">
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
        "y la contraseña que te indicó el administrador.\n"
        f"{panel_cta_plain()}"
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
          {panel_cta_html("Ingresar al panel")}
          <p style="margin:14px 0 0;line-height:1.6;">
            Si tienes dudas, nuestro equipo de soporte está disponible para ayudarte.
          </p>
"""
    return send_branded_email(subject, to_email, plain_body, content_html)


def send_provider_account_notice_email(
    to_email: str,
    *,
    provider_name: str,
    title: str,
    detail: str,
    actor_label: str,
    is_admin_copy: bool = False,
) -> bool:
    """Correo de cuenta proveedor (reactivar/suspender/etc.) con plantilla y logo."""
    display_name = (provider_name or "").strip() or "proveedor(a)"
    subject = f"Ferragro - {title}"
    if is_admin_copy:
        plain_body = (
            f"{title}\n\n"
            f"Proveedor: {display_name}\n"
            f"Correo del proveedor: {normalize_email(to_email) or to_email}\n\n"
            f"{detail}\n\n"
            f"Realizado por: {actor_label}.\n"
            f"{panel_cta_plain()}"
            f"Soporte: {SUPPORT_EMAIL} | WhatsApp: {SUPPORT_PHONE}\n"
            f"Direccion: {COMPANY_ADDRESS}\n"
            f"Sitio web: {COMPANY_WEBSITE}\n\n"
            "Ferragro"
        )
        safe_detail = detail.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br />")
        content_html = f"""
          <h1 style="margin:0 0 16px;font-size:22px;color:#0f6e2f;">{title.replace("<", "&lt;")}</h1>
          <p style="margin:0 0 8px;line-height:1.6;"><strong>Proveedor:</strong> {display_name}</p>
          <p style="margin:0 0 14px;line-height:1.6;"><strong>Correo:</strong> {normalize_email(to_email) or to_email}</p>
          <p style="margin:0 0 14px;line-height:1.6;">{safe_detail}</p>
          <p style="margin:0;line-height:1.6;">Realizado por: {actor_label}.</p>
          {panel_cta_html("Ver detalle en el panel")}
"""
    else:
        plain_body = (
            f"Hola {display_name},\n\n"
            f"{detail}\n\n"
            f"Acción registrada por: {actor_label}.\n\n"
            "Si no reconoces este cambio, contacta a soporte Ferragro.\n"
            f"{panel_cta_plain()}"
            f"Soporte: {SUPPORT_EMAIL} | WhatsApp: {SUPPORT_PHONE}\n"
            f"Direccion: {COMPANY_ADDRESS}\n"
            f"Sitio web: {COMPANY_WEBSITE}\n\n"
            "Ferragro"
        )
        safe_detail = detail.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br />")
        content_html = f"""
          <h1 style="margin:0 0 16px;font-size:22px;color:#0f6e2f;">{title.replace("<", "&lt;")}</h1>
          <p style="margin:0 0 14px;line-height:1.6;">Hola <strong>{display_name}</strong>,</p>
          <p style="margin:0 0 14px;line-height:1.6;">{safe_detail}</p>
          <p style="margin:0;line-height:1.6;">Acción registrada por: {actor_label}.</p>
          {panel_cta_html("Ingresar al panel")}
"""
    return send_branded_email(subject, to_email, plain_body, content_html)


def send_notification_email(to_email: str, title: str, message: str) -> bool:
    subject = f"Ferragro - {title}"
    plain_body = (
        f"{title}\n\n"
        f"{message}\n\n"
        f"{panel_cta_plain()}"
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
          {panel_cta_html("Ver detalle en el panel")}
"""
    return send_branded_email(subject, to_email, plain_body, content_html)


def send_notification_email_with_retry(
    to_email: str,
    title: str,
    message: str,
    *,
    max_attempts: int = 3,
) -> bool:
    from app.services.email_delivery import deliver_with_retry

    subject = f"Ferragro - {title}"
    result = deliver_with_retry(
        lambda: send_notification_email(to_email, title, message),
        recipient=normalize_email(to_email) or to_email,
        subject=subject,
        kind="notification",
        max_attempts=max_attempts,
    )
    return result.ok
