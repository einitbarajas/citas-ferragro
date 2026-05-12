"""Utilidad simple de correo SMTP (fallback a logs en desarrollo)."""
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
import smtplib

from app.core.config import settings

SUPPORT_EMAIL = "ecommerce@ferragro.com"
SUPPORT_PHONE = "+57 3142254819"
SUPPORT_WHATSAPP_URL = "https://wa.me/573142254819"
COMPANY_ADDRESS = "Carrera 41 #46-167, Itagui-Ant"
COMPANY_WEBSITE = "https://www.ferragro.com"
LOGO_PATH = Path(__file__).resolve().parents[3] / "frontend" / "public" / "ferragro-blan-bord.png"
LOGO_CID = "ferragro-logo-watermark"


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
    html_body = _build_mail_layout(content_html)

    if not settings.smtp_host or not settings.smtp_from_email:
        print(f"[mail-fallback] To: {to_email} | Subject: {subject} | Body: {plain_body}")
        return True

    message = MIMEMultipart("related")
    message["Subject"] = subject
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = to_email
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

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        client.sendmail(settings.smtp_from_email, [to_email], message.as_string())
    return True


def send_temporary_password_email(to_email: str, temporary_password: str) -> bool:
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
    return send_branded_email(subject, to_email, plain_body, content_html)


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
