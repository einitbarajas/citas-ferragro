"""Normalización y validación de correos (independiente del proveedor del destinatario)."""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str | None) -> str | None:
    """
    Limpia el correo para envío: quita espacios, extrae de formato 'Nombre <correo@dominio>'.
    El dominio del destinatario (Gmail, Outlook, etc.) no cambia el envío.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "<" in text and ">" in text:
        start = text.index("<") + 1
        end = text.index(">")
        text = text[start:end].strip()
    return text


def is_deliverable_email(value: str | None) -> bool:
    email = normalize_email(value)
    if not email:
        return False
    return bool(_EMAIL_RE.match(email))


def dedupe_emails(emails: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for raw in emails:
        email = normalize_email(raw)
        if not email or not is_deliverable_email(email):
            continue
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(email)
    return unique
