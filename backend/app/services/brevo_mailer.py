"""Envío por API Brevo (HTTPS). Remitente verificado por enlace en Gmail, sin dominio DNS."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app.core.config import settings
from app.services.email_utils import is_deliverable_email, normalize_email

logger = logging.getLogger(__name__)

_BREVO_URL = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT_SECONDS = 20


def brevo_configured() -> bool:
    return settings.brevo_send_ready


def send_brevo_email(
    *,
    to_email: str,
    subject: str,
    plain_body: str,
    html_body: str,
) -> bool:
    delivery = normalize_email(to_email)
    if not delivery or not is_deliverable_email(delivery):
        logger.warning("Brevo omitido (destinatario inválido): %r", to_email)
        return False
    if not brevo_configured():
        return False

    from_email = normalize_email(settings.smtp_from_email) or normalize_email(settings.resend_from_email)
    if not from_email:
        logger.error("Brevo sin remitente (SMTP_FROM_EMAIL)")
        return False

    payload = {
        "sender": {"name": settings.smtp_from_name, "email": from_email},
        "to": [{"email": delivery}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": plain_body,
    }
    reply_to = normalize_email(settings.smtp_reply_to)
    if reply_to:
        payload["replyTo"] = {"email": reply_to}

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        _BREVO_URL,
        data=data,
        method="POST",
        headers={
            "api-key": settings.brevo_api_key.strip(),
            "Content-Type": "application/json",
            "accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        logger.error("Brevo HTTP %s para %s: %s", exc.code, delivery, body)
        return False
    except Exception:
        logger.exception("Brevo falló para %s", delivery)
        return False
