"""Bloqueo temporal por intentos fallidos de autenticación."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.login_attempt import LoginAttempt


def _now():
    return datetime.now(timezone.utc)


def is_login_blocked(db: Session, credential_id: int) -> tuple[bool, datetime | None]:
    row = db.get(LoginAttempt, credential_id)
    if not row or not row.blocked_until:
        return False, None
    if row.blocked_until <= _now():
        row.blocked_until = None
        row.consecutive_failures = 0
        return False, None
    return True, row.blocked_until


def record_login_failure(db: Session, credential_id: int) -> None:
    row = db.get(LoginAttempt, credential_id)
    if not row:
        row = LoginAttempt(credential_id=credential_id, consecutive_failures=0, blocked_until=None)
        db.add(row)
        db.flush()
    row.consecutive_failures += 1
    if row.consecutive_failures >= settings.login_max_attempts:
        row.blocked_until = _now() + timedelta(minutes=settings.login_lockout_minutes)


def reset_login_failures(db: Session, credential_id: int) -> None:
    row = db.get(LoginAttempt, credential_id)
    if row:
        row.consecutive_failures = 0
        row.blocked_until = None
