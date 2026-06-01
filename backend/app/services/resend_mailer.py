"""Envío de correo vía Resend (HTTPS). Necesario en Render plan free (bloquea SMTP 587/465)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.config import settings
from app.services.email_delivery_log import record_delivery
from app.services.email_sandbox import (
    redirect_recipient_for_sandbox,
    resend_sandbox_inbox_candidates,
)
from app.services.email_utils import is_deliverable_email, normalize_email

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT_SECONDS = 25


@dataclass(frozen=True)
class ResendSendResult:
    ok: bool
    delivery_to: str
    original_to: str
    resend_id: str | None = None
    error: str | None = None


def resend_configured() -> bool:
    return bool(settings.resend_api_key.strip())


def _from_header() -> str | None:
    if settings.resend_sandbox:
        return f"{settings.smtp_from_name} <onboarding@resend.dev>"
    from_email = normalize_email(settings.resend_from_email) or normalize_email(settings.smtp_from_email)
    if not from_email:
        logger.error("Resend sin remitente (RESEND_FROM_EMAIL o dominio verificado en resend.com)")
        return None
    return f"{settings.smtp_from_name} <{from_email}>"


def _post_resend(
    *,
    delivery: str,
    subject: str,
    plain_body: str,
    html_body: str,
    email_kind: str | None,
) -> ResendSendResult:
    from_header = _from_header()
    if not from_header:
        return ResendSendResult(
            ok=False,
            delivery_to=delivery,
            original_to=delivery,
            error="missing_from",
        )

    payload: dict = {
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
            raw = response.read().decode("utf-8", errors="replace")
            if not (200 <= response.status < 300):
                return ResendSendResult(
                    ok=False,
                    delivery_to=delivery,
                    original_to=delivery,
                    error=f"http_{response.status}",
                )
            resend_id = None
            try:
                body = json.loads(raw) if raw else {}
                resend_id = str(body.get("id") or "") or None
            except json.JSONDecodeError:
                pass
            return ResendSendResult(
                ok=True,
                delivery_to=delivery,
                original_to=delivery,
                resend_id=resend_id,
            )
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:500]
        logger.error("Resend HTTP %s para %s: %s", exc.code, delivery, err_body)
        return ResendSendResult(
            ok=False,
            delivery_to=delivery,
            original_to=delivery,
            error=f"http_{exc.code}:{err_body[:120]}",
        )
    except Exception as exc:
        logger.exception("Resend falló para %s", delivery)
        return ResendSendResult(
            ok=False,
            delivery_to=delivery,
            original_to=delivery,
            error=f"{type(exc).__name__}",
        )


def send_resend_email(
    *,
    to_email: str,
    subject: str,
    plain_body: str,
    html_body: str,
    email_kind: str | None = None,
) -> bool:
    original_to = normalize_email(to_email)
    if not original_to or not is_deliverable_email(original_to):
        logger.warning("Resend omitido (destinatario inválido): %r", to_email)
        return False
    if not resend_configured():
        return False

    delivery, plain_body = redirect_recipient_for_sandbox(original_to, plain_body)
    if delivery != original_to:
        html_body = (
            f'<p style="margin:0 0 12px;color:#666;font-size:13px;">'
            f"Destinatario original: {original_to}</p>"
            + html_body
        )

    attempts: list[tuple[str, str, str]] = []
    seen_targets: set[str] = set()

    def _add_attempt(target: str, p: str, h: str) -> None:
        key = target.lower()
        if key in seen_targets:
            return
        seen_targets.add(key)
        attempts.append((target, p, h))

    _add_attempt(delivery, plain_body, html_body)
    if settings.resend_sandbox:
        if original_to.lower() != delivery.lower():
            _add_attempt(original_to, plain_body, html_body)
        for inbox in resend_sandbox_inbox_candidates():
            note_plain = f"[Reintento sandbox — destinatario original: {original_to}]\n\n{plain_body}"
            note_html = (
                f'<p style="color:#666;font-size:13px;">Destinatario original: {original_to}</p>'
                + html_body
            )
            _add_attempt(inbox, note_plain, note_html)

    last_error: str | None = None
    for idx, (target, p_body, h_body) in enumerate(attempts):
        result = _post_resend(
            delivery=target,
            subject=subject,
            plain_body=p_body,
            html_body=h_body,
            email_kind=email_kind,
        )
        if result.ok:
            record_delivery(
                kind=email_kind or "resend",
                to=target,
                original_to=original_to if target.lower() != original_to.lower() else None,
                subject=subject,
                provider="resend",
                ok=True,
                attempts=idx + 1,
                resend_id=result.resend_id,
            )
            if target.lower() != original_to.lower():
                logger.info(
                    "Resend sandbox entregó a %s (solicitado %s) kind=%s id=%s",
                    target,
                    original_to,
                    email_kind,
                    result.resend_id,
                )
            return True
        last_error = result.error

    record_delivery(
        kind=email_kind or "resend",
        to=delivery,
        original_to=original_to,
        subject=subject,
        provider="resend",
        ok=False,
        attempts=len(attempts),
        error=last_error,
    )
    return False
