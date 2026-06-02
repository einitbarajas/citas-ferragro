"""Logo y plantilla compartida para correos (SMTP y Resend)."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Debe coincidir exactamente entre <img src="cid:..."> y Content-ID del adjunto SMTP.
LOGO_CID = "ferragro-logo"
LOGO_FILENAME = "ferragro-logo.png"
DEFAULT_API_BASE = "https://ferragro-api.onrender.com"
LOGO_GITHUB_RAW = (
    "https://raw.githubusercontent.com/einitbarajas/citas-ferragro/main/"
    "backend/static/ferragro-logo.png"
)
_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
_LOGO_CANDIDATES = (
    _STATIC_DIR / "ferragro-logo.png",
    _STATIC_DIR / "ferragro-blan-bord.png",
    Path(__file__).resolve().parents[3] / "frontend" / "public" / "ferragro-logo.png",
    Path(__file__).resolve().parents[3] / "frontend" / "public" / "ferragro-blan-bord.png",
)
LOGO_PATH = next((p for p in _LOGO_CANDIDATES if p.is_file()), _LOGO_CANDIDATES[0])

_LOGO_IMG_STYLE = "width:260px;max-width:100%;height:auto;display:block;margin:0 auto;"


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
    """URL HTTPS absoluta del logo (compatible con Gmail vía Resend/Brevo)."""
    configured = str(getattr(settings, "public_logo_url", "") or "").strip()
    if configured:
        return configured
    api_base = str(getattr(settings, "public_api_url", "") or "").strip() or DEFAULT_API_BASE
    return f"{api_base.rstrip('/')}/assets/ferragro-logo.png"


def logo_data_uri() -> str | None:
    raw = read_logo_bytes()
    if not raw:
        return None
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def logo_img_html(*, use_cid: bool) -> str:
    """
    SMTP: inline CID (MIME related).
    Resend/Brevo: URL HTTPS pública (Gmail no muestra bien cid: ni data: en muchos casos).
    """
    if use_cid:
        return f'<img src="cid:{LOGO_CID}" alt="Ferragro" style="{_LOGO_IMG_STYLE}" />'
    url = hosted_logo_url()
    return f'<img src="{url}" alt="Ferragro" style="{_LOGO_IMG_STYLE}" />'


def resend_logo_attachment() -> dict | None:
    """
    Adjunto inline opcional (solo si el HTML usa cid:).
    Resend/Brevo usan URL HTTPS en el HTML; no hace falta adjunto.
    """
    return None
