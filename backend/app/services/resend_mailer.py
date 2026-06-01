"""Envío de correo vía Resend (HTTPS). Necesario en Render plan free (bloquea SMTP 587/465)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app.core.config import settings
from app.services.email_sandbox import redirect_recipient_for_sandbox, resend_sandbox_inbox
from app.services.email_utils import is_deliverable_email, normalize_email

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT_SECONDS = 20


def resend_configured() -> bool:
    return bool(settings.resend_api_key.strip())


def send_resend_email(
    *,
    to_email: str,
    subject: str,
    plain_body: str,
    html_body: str,
    email_kind: str | None = None,
    *,
    _sandbox_retry: bool = True,
) -> bool:
    delivery = normalize_email(to_email)
    if not delivery or not is_deliverable_email(delivery):
        logger.warning("Resend omitido (destinatario inválido): %r", to_email)
        return False
    if not resend_configured():
        return False

    original_to = delivery
    delivery, plain_body = redirect_recipient_for_sandbox(delivery, plain_body)
    if delivery != original_to:
        html_body = (
            f'<p style="margin:0 0 12px;color:#666;font-size:13px;">'
            f"Destinatario original: {original_to}</p>"
            + html_body
        )

    if settings.resend_sandbox:
        from_header = f"{settings.smtp_from_name} <onboarding@resend.dev>"
    else:
        from_email = normalize_email(settings.resend_from_email) or normalize_email(settings.smtp_from_email)
        if not from_email:
            logger.error("Resend sin remitente (RESEND_FROM_EMAIL o dominio verificado en resend.com)")
            return False
        from_header = f"{settings.smtp_from_name} <{from_email}>"
    payload = {
        "from": from_header,
        "to": [delivery],
        "subject": subject,
        "html": html_body,
        "text": plain_body,
    }
    reply_to = normalize_email(settings.smtp_reply_to)
    if reply_to:
        payload["reply_to"] = reply_to
    if email_kind:
        payload["tags"] = [{"name": "kind", "value": email_kind[:50]}]

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        _RESEND_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "ferragro-api",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            ok = 200 <= response.status < 300
            if not ok:
                logger.error("Resend respondió %s para %s", response.status, delivery)
            return ok
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        logger.error("Resend HTTP %s para %s: %s", exc.code, delivery, body)
        if (
            _sandbox_retry
            and settings.resend_sandbox
            and exc.code in (403, 422)
        ):
            inbox = resend_sandbox_inbox()
            if inbox and delivery.lower() != inbox.lower():
                logger.warning(
                    "Resend sandbox: reintento de %s -> %s (kind=%s)",
                    delivery,
                    inbox,
                    email_kind,
                )
                return send_resend_email(
                    to_email=inbox,
                    subject=subject,
                    plain_body=(
                        f"[Reintento sandbox — no se pudo entregar a {original_to}]\n\n{plain_body}"
                    ),
                    html_body=html_body,
                    email_kind=email_kind,
                    _sandbox_retry=False,
                )
            logger.error(
                "Resend sandbox solo entrega al inbox de la cuenta. "
                "Define RESEND_SANDBOX_INBOX en Render."
            )
        return False
    except Exception:
        logger.exception("Resend falló para %s", delivery)
        return False
