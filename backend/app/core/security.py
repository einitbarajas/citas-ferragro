from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
import uuid

import bcrypt
from jose import jwt

from app.core.config import settings


def _looks_like_bcrypt_hash(hashed_password: str) -> bool:
    """bcrypt modular crypt format: $2[aby]$... (evita ValueError: Invalid salt con texto plano en BD)."""
    if not hashed_password or len(hashed_password) < 59:
        return False
    return hashed_password.startswith(("$2a$", "$2b$", "$2y$"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not _looks_like_bcrypt_hash(hashed_password):
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "role": role, "exp": expire, "token_type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(
    subject: str,
    role: str,
    *,
    jti: UUID | None = None,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, UUID]:
    """Devuelve (jwt_refresh, jti). El JTI debe persistirse para invalidar sesiones."""
    token_jti = jti or uuid.uuid4()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
        "token_type": "refresh",
        "jti": str(token_jti),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, token_jti
