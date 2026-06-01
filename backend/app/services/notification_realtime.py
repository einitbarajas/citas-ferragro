"""Bus de eventos SSE para notificaciones en tiempo real."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class _Subscriber:
    queue: asyncio.Queue
    role: str
    subject: str
    warehouse_ids: frozenset[int] = field(default_factory=frozenset)


_subscribers: list[_Subscriber] = []
_lock = asyncio.Lock()


async def subscribe_user(
    *,
    role: str,
    subject: str,
    warehouse_ids: frozenset[int] | None = None,
) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    sub = _Subscriber(queue=queue, role=role, subject=subject, warehouse_ids=warehouse_ids or frozenset())
    async with _lock:
        _subscribers.append(sub)
    return queue


async def unsubscribe_user(queue: asyncio.Queue) -> None:
    async with _lock:
        _subscribers[:] = [s for s in _subscribers if s.queue is not queue]


def _should_deliver(sub: _Subscriber, *, warehouse_id: int, provider_id: int) -> bool:
    from app.models.user import UserRole

    if sub.role == UserRole.admin:
        return True
    if sub.role in (UserRole.logistica, UserRole.admin_bodega):
        return warehouse_id in sub.warehouse_ids
    if sub.role == UserRole.proveedor:
        return sub.subject == str(provider_id)
    return False


async def broadcast_notification_event(payload: dict[str, Any]) -> None:
    warehouse_id = int(payload.get("warehouse_id") or 0)
    provider_id = int(payload.get("provider_id") or 0)
    data = json.dumps(payload, default=str)
    message = f"data: {data}\n\n"

    async with _lock:
        targets = list(_subscribers)

    for sub in targets:
        if not _should_deliver(sub, warehouse_id=warehouse_id, provider_id=provider_id):
            continue
        try:
            sub.queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.debug("SSE queue full for %s:%s", sub.role, sub.subject)
