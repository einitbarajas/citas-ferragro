"""Carga SMTP desde archivos secretos de Render antes de instanciar Settings."""
from __future__ import annotations

import os
from pathlib import Path


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        key = key.strip()
        if not key.startswith("SMTP_"):
            continue
        value = raw.strip().strip('"').strip("'").replace("\r", "").replace("\n", "")
        if key == "SMTP_PASSWORD" and value:
            value = value.replace(" ", "")
        if value:
            values[key] = value
    return values


def _smtp_needs_secret_files() -> bool:
    required = ("SMTP_HOST", "SMTP_FROM_EMAIL", "SMTP_USER", "SMTP_PASSWORD")
    return any(not _smtp_env_nonempty(key) for key in required)


def _smtp_env_nonempty(key: str) -> bool:
    return bool(os.getenv(key, "").strip())


def bootstrap_smtp_from_secret_files(*, overlay: bool = False) -> list[str]:
    """
    Lee /etc/secrets/smtp.env (Render) u otros paths.
    overlay=True: en producción re-aplica el archivo aunque ya existan vars (corrige password vieja).
    """
    if not overlay and not _smtp_needs_secret_files():
        return []

    backend_dir = Path(__file__).resolve().parents[2]
    repo_root = backend_dir.parent
    candidates = [
        Path("/etc/secrets/smtp.env"),
        Path("/etc/secrets/smtp-render.env"),
        Path("/etc/secrets/.env"),
        backend_dir / "smtp.env",
        backend_dir / "smtp-render.env",
        repo_root / "smtp-render.env",
    ]
    secret_dir = Path("/etc/secrets")
    if secret_dir.is_dir():
        candidates.extend(sorted(secret_dir.glob("*.env")))

    applied: list[str] = []
    for path in candidates:
        if not path.is_file():
            continue
        for key, value in _parse_env_file(path).items():
            if overlay or not os.getenv(key, "").strip():
                os.environ[key] = value
        applied.append(str(path))
        if (
            os.getenv("SMTP_HOST", "").strip()
            and os.getenv("SMTP_FROM_EMAIL", "").strip()
            and os.getenv("SMTP_USER", "").strip()
            and os.getenv("SMTP_PASSWORD", "").strip()
        ):
            break
    return applied
