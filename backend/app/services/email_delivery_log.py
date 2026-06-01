"""Registro en memoria de envíos transaccionales (métricas y diagnóstico)."""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

_MAX_ENTRIES = 500
_lock = threading.Lock()
_entries: deque[dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)
_stats = {"ok": 0, "fail": 0}


@dataclass(frozen=True)
class EmailLogEntry:
    ts: str
    kind: str
    to: str
    original_to: str | None
    subject: str
    provider: str
    ok: bool
    attempts: int
    error: str | None = None
    resend_id: str | None = None


def record_delivery(
    *,
    kind: str,
    to: str,
    subject: str,
    provider: str,
    ok: bool,
    attempts: int = 1,
    original_to: str | None = None,
    error: str | None = None,
    resend_id: str | None = None,
) -> None:
    entry = EmailLogEntry(
        ts=datetime.now(timezone.utc).isoformat(),
        kind=kind,
        to=to,
        original_to=original_to,
        subject=subject[:120],
        provider=provider,
        ok=ok,
        attempts=attempts,
        error=error,
        resend_id=resend_id,
    )
    with _lock:
        _entries.append(asdict(entry))
        if ok:
            _stats["ok"] += 1
        else:
            _stats["fail"] += 1


def recent_entries(limit: int = 50) -> list[dict[str, Any]]:
    with _lock:
        items = list(_entries)
    return items[-limit:][::-1]


def delivery_stats() -> dict[str, int]:
    with _lock:
        return dict(_stats)
