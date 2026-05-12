"""Rate limiting (slowapi) — instancia única para la app y rutas sensibles."""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute_default}/minute"],
    enabled=settings.rate_limit_enabled,
)
