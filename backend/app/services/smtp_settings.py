"""Normalización SMTP (Gmail en Render, contraseñas de aplicación, remitente)."""
from __future__ import annotations

import logging

from app.core.config import Settings
from app.services.email_utils import normalize_email

logger = logging.getLogger(__name__)


def finalize_smtp_settings(target: Settings) -> None:
    """Alinea credenciales tras leer env / secret files."""
    password = str(target.smtp_password or "").strip()
    if password:
        # Contraseñas de aplicación Gmail suelen pegarse con espacios.
        object.__setattr__(target, "smtp_password", password.replace(" ", ""))

    host = (target.smtp_host or "").strip().lower()
    if "gmail.com" not in host:
        return

    user = normalize_email(target.smtp_user) or ""
    from_email = normalize_email(target.smtp_from_email) or ""
    if user and not from_email:
        object.__setattr__(target, "smtp_from_email", user)
    elif from_email and not user:
        object.__setattr__(target, "smtp_user", from_email)
    elif user and from_email and user.lower() != from_email.lower():
        logger.warning(
            "Gmail exige que SMTP_FROM_EMAIL coincida con SMTP_USER; usando %s",
            user,
        )
        object.__setattr__(target, "smtp_from_email", user)

    if not target.smtp_use_ssl and int(target.smtp_port) == 587:
        object.__setattr__(target, "smtp_profile", target.smtp_profile or "gmail")
