"""Elige la configuración SMTP que Gmail acepta en Render (env vs secret, 587 vs 465)."""
from __future__ import annotations

import logging
import smtplib
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from app.core.config import refresh_smtp_settings, settings
from app.services.email_utils import normalize_email

logger = logging.getLogger(__name__)

_SMTP_TIMEOUT = 10
_resolved_label: str | None = None


@dataclass(frozen=True)
class _SmtpCandidate:
    label: str
    force_secret_overlay: bool
    use_ssl: bool
    port: int
    use_tls: bool


_CANDIDATES: tuple[_SmtpCandidate, ...] = (
    _SmtpCandidate("env_starttls_587", False, False, 587, True),
    _SmtpCandidate("secret_starttls_587", True, False, 587, True),
    _SmtpCandidate("env_ssl_465", False, True, 465, False),
    _SmtpCandidate("secret_ssl_465", True, True, 465, False),
)


@contextmanager
def _probe_client(
    *,
    use_ssl: bool,
    port: int,
    use_tls: bool,
) -> Iterator[smtplib.SMTP]:
    host = settings.smtp_host
    user = settings.smtp_user
    password = settings.smtp_password
    if use_ssl:
        client = smtplib.SMTP_SSL(host, port, timeout=_SMTP_TIMEOUT)
        try:
            client.ehlo()
            if user:
                client.login(user, password)
            yield client
        finally:
            client.quit()
        return

    client = smtplib.SMTP(host, port, timeout=_SMTP_TIMEOUT)
    try:
        client.ehlo()
        if use_tls:
            client.starttls()
            client.ehlo()
        if user:
            client.login(user, password)
        yield client
    finally:
        client.quit()


def _apply_candidate(candidate: _SmtpCandidate) -> None:
    refresh_smtp_settings(force_secret_overlay=candidate.force_secret_overlay)
    object.__setattr__(settings, "smtp_use_ssl", candidate.use_ssl)
    object.__setattr__(settings, "smtp_port", candidate.port)
    object.__setattr__(settings, "smtp_use_tls", candidate.use_tls)
    user = normalize_email(settings.smtp_user) or ""
    if user:
        object.__setattr__(settings, "smtp_from_email", user)


def _try_login(candidate: _SmtpCandidate) -> bool:
    if not settings.smtp_send_ready:
        return False
    _apply_candidate(candidate)
    try:
        with _probe_client(
            use_ssl=candidate.use_ssl,
            port=candidate.port,
            use_tls=candidate.use_tls,
        ):
            return True
    except Exception as exc:
        logger.warning("SMTP candidato %s falló: %s", candidate.label, exc)
        return False


def ensure_smtp_login_ready(*, force: bool = False) -> bool:
    """Prueba env/secret y 587/465; deja activa la primera combinación que Gmail acepte."""
    global _resolved_label
    if _resolved_label and not force:
        for candidate in _CANDIDATES:
            if candidate.label == _resolved_label:
                _apply_candidate(candidate)
                return True

    if not settings.smtp_send_ready and not refresh_smtp_settings():
        return False

    for candidate in _CANDIDATES:
        if _try_login(candidate):
            _resolved_label = candidate.label
            logger.info("SMTP operativo en Render con perfil %s", candidate.label)
            return True

    _resolved_label = None
    return False


def resolved_smtp_label() -> str | None:
    return _resolved_label
