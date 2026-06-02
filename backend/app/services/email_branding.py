"""Logo y plantilla compartida para correos (SMTP y Resend)."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Debe coincidir entre <img src="cid:..."> y content_id del adjunto (SMTP y Resend).
LOGO_CID = "ferragro-logo"
# PNG con fondo blanco (#fff): Gmail y Outlook no pintan negro en transparencias.
LOGO_FILENAME = "ferragro-logo-email.png"
DEFAULT_API_BASE = "https://ferragro-api.onrender.com"
LOGO_CACHE_BUSTER = "20260602-nuevo"
DEFAULT_LOGO_URL = f"https://citas.ferragro.vercel.app/ferragro-logo-email.png?v={LOGO_CACHE_BUSTER}"
LOGO_GITHUB_RAW = (
    "https://raw.githubusercontent.com/einitbarajas/citas-ferragro/main/"
    "backend/static/ferragro-logo-email.png"
)
_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
_PUBLIC_DIR = Path(__file__).resolve().parents[3] / "frontend" / "public"
_LOGO_CANDIDATES = (
    _STATIC_DIR / "ferragro-logo-email.png",
    _PUBLIC_DIR / "ferragro-logo-email.png",
    _STATIC_DIR / "ferragro-logo.png",
    _PUBLIC_DIR / "ferragro-logo.png",
)
LOGO_PATH = next((p for p in _LOGO_CANDIDATES if p.is_file()), _LOGO_CANDIDATES[0])

_LOGO_IMG_STYLE = (
    "width:260px;max-width:100%;height:auto;display:block;margin:0 auto;"
    "border:0;outline:none;"
)


def read_logo_bytes() -> bytes | None:
    for path in _LOGO_CANDIDATES:
        if not path.is_file():
            continue
        try:
            return path.read_bytes()
        except Exception:
            logger.exception("No se pudo leer logo: %s", path)
    return None


def hosted_logo_url() -> str:
    """URL HTTPS absoluta del logo (Resend/Brevo cuando no se usa CID)."""
    configured = str(getattr(settings, "public_logo_url", "") or "").strip()
    if configured:
        return configured
    panel = str(getattr(settings, "public_panel_url", "") or "").strip().rstrip("/")
    if panel:
        return f"{panel}/ferragro-logo-email.png?v={LOGO_CACHE_BUSTER}"
    return DEFAULT_LOGO_URL


def logo_img_html(*, use_cid: bool) -> str:
    if use_cid:
        img = f'<img src="cid:{LOGO_CID}" alt="Ferragro" style="{_LOGO_IMG_STYLE}" />'
    else:
        url = hosted_logo_url()
        img = f'<img src="{url}" alt="Ferragro" style="{_LOGO_IMG_STYLE}" />'
    return (
        '<div style="background:#ffffff;padding:0 0 4px;margin:0;">'
        f"{img}"
        "</div>"
    )


def resend_logo_attachment() -> dict | None:
    """Adjunto inline para Resend (obligatorio si el HTML usa cid:)."""
    raw = read_logo_bytes()
    if not raw:
        remote = str(getattr(settings, "public_logo_url", "") or "").strip() or hosted_logo_url()
        return {
            "filename": LOGO_FILENAME,
            "path": remote,
            "content_id": LOGO_CID,
        }
    return {
        "filename": LOGO_FILENAME,
        "content": base64.b64encode(raw).decode("ascii"),
        "content_id": LOGO_CID,
    }
