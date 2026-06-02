"""Logo y plantilla compartida para correos (SMTP y Resend)."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Debe coincidir entre <img src="cid:..."> y content_id del adjunto (SMTP y Resend).
LOGO_CID = "ferragro-logo"
LOGO_FILENAME = "ferragro-logo.png"
DEFAULT_API_BASE = "https://ferragro-api.onrender.com"
# Vercel sirve el PNG en producción (Gmail lo carga mejor que GitHub raw).
DEFAULT_LOGO_URL = "https://citas.ferragro.vercel.app/ferragro-logo.png"
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
    """URL HTTPS absoluta del logo (Resend/Brevo cuando no se usa CID)."""
    configured = str(getattr(settings, "public_logo_url", "") or "").strip()
    if configured:
        return configured
    panel = str(getattr(settings, "public_panel_url", "") or "").strip().rstrip("/")
    if panel:
        return f"{panel}/ferragro-logo.png"
    return DEFAULT_LOGO_URL


def logo_img_html(*, use_cid: bool) -> str:
    if use_cid:
        return f'<img src="cid:{LOGO_CID}" alt="Ferragro" style="{_LOGO_IMG_STYLE}" />'
    url = hosted_logo_url()
    return f'<img src="{url}" alt="Ferragro" style="{_LOGO_IMG_STYLE}" />'


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
