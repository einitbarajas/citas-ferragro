"""Logo y plantilla compartida para correos (SMTP y Resend)."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

LOGO_CID_LIGHT = "ferragro-logo-light"
LOGO_CID_DARK = "ferragro-logo-dark"
LOGO_CID = LOGO_CID_LIGHT  # compat tests / logs
LOGO_FILENAME_LIGHT = "ferragro-logo-email-light.png"
LOGO_FILENAME_DARK = "ferragro-logo-email-dark.png"
LOGO_CACHE_BUSTER = "20260602-dual"
DEFAULT_API_BASE = "https://ferragro-api.onrender.com"
_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
_PUBLIC_DIR = Path(__file__).resolve().parents[3] / "frontend" / "public"

_LOGO_IMG_STYLE = (
    "width:260px;max-width:100%;height:auto;display:block;margin:0 auto;"
    "border:0;outline:none;"
)

_EMAIL_HEAD_STYLES = """
<meta name="color-scheme" content="light dark" />
<meta name="supported-color-schemes" content="light dark" />
<style type="text/css">
  .ferragro-logo-light { display:block !important; max-height:none !important; overflow:visible !important; }
  .ferragro-logo-dark { display:none !important; max-height:0 !important; overflow:hidden !important; }
  @media (prefers-color-scheme: dark) {
    .ferragro-logo-light { display:none !important; max-height:0 !important; overflow:hidden !important; }
    .ferragro-logo-dark { display:block !important; max-height:none !important; overflow:visible !important; }
    .ferragro-email-card { background-color:#2d2d2d !important; border-color:#444444 !important; }
    .ferragro-email-body { background-color:#1a1a1a !important; color:#e8eaed !important; }
    .ferragro-email-footer { border-color:#444444 !important; }
    .ferragro-email-link { color:#81c995 !important; }
    .ferragro-email-brand { color:#81c995 !important; }
  }
</style>
"""


def _read_file(path: Path) -> bytes | None:
    if not path.is_file():
        return None
    try:
        return path.read_bytes()
    except Exception:
        logger.exception("No se pudo leer logo: %s", path)
        return None


def read_logo_bytes_light() -> bytes | None:
    for name in (LOGO_FILENAME_LIGHT, "ferragro-logo-email.png"):
        raw = _read_file(_STATIC_DIR / name)
        if raw:
            return raw
        raw = _read_file(_PUBLIC_DIR / name)
        if raw:
            return raw
    return None


def read_logo_bytes_dark() -> bytes | None:
    for path in (_STATIC_DIR / LOGO_FILENAME_DARK, _PUBLIC_DIR / LOGO_FILENAME_DARK):
        raw = _read_file(path)
        if raw:
            return raw
    return None


def read_logo_bytes() -> bytes | None:
    """Compat: versión modo claro."""
    return read_logo_bytes_light()


LOGO_PATH = _STATIC_DIR / LOGO_FILENAME_LIGHT


def hosted_logo_url(*, dark: bool = False) -> str:
    panel = str(getattr(settings, "public_panel_url", "") or "").strip().rstrip("/")
    base = panel or "https://citas.ferragro.vercel.app"
    fname = LOGO_FILENAME_DARK if dark else LOGO_FILENAME_LIGHT
    return f"{base}/{fname}?v={LOGO_CACHE_BUSTER}"


def logo_img_html(*, use_cid: bool) -> str:
    if use_cid:
        light_src = f"cid:{LOGO_CID_LIGHT}"
        dark_src = f"cid:{LOGO_CID_DARK}"
    else:
        light_src = hosted_logo_url(dark=False)
        dark_src = hosted_logo_url(dark=True)

    light_img = (
        f'<img class="ferragro-logo-light" src="{light_src}" alt="Ferragro" '
        f'style="{_LOGO_IMG_STYLE}" />'
    )
    dark_img = (
        f'<img class="ferragro-logo-dark" src="{dark_src}" alt="Ferragro" '
        f'style="{_LOGO_IMG_STYLE}" />'
    )
    return (
        f"{_EMAIL_HEAD_STYLES}"
        '<div style="padding:0 0 4px;margin:0;line-height:0;background:transparent;">'
        f"{light_img}{dark_img}"
        "</div>"
    )


def resend_logo_attachments() -> list[dict]:
    out: list[dict] = []
    light = read_logo_bytes_light()
    dark = read_logo_bytes_dark()
    if light:
        out.append(
            {
                "filename": LOGO_FILENAME_LIGHT,
                "content": base64.b64encode(light).decode("ascii"),
                "content_id": LOGO_CID_LIGHT,
            }
        )
    if dark:
        out.append(
            {
                "filename": LOGO_FILENAME_DARK,
                "content": base64.b64encode(dark).decode("ascii"),
                "content_id": LOGO_CID_DARK,
            }
        )
    return out


def resend_logo_attachment() -> dict | None:
    """Primer adjunto (compat); usar resend_logo_attachments()."""
    attachments = resend_logo_attachments()
    return attachments[0] if attachments else None
