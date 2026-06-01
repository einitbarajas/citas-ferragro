"""Bloqueo temporal por intentos fallidos de autenticación."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.login_attempt import LoginAttempt


@dataclass(frozen=True)
class LoginFailureOutcome:
    consecutive_failures: int
    just_blocked: bool


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


def record_login_failure(db: Session, credential_id: int) -> LoginFailureOutcome:
    row = db.get(LoginAttempt, credential_id)
    if not row:
        row = LoginAttempt(credential_id=credential_id, consecutive_failures=0, blocked_until=None)
        db.add(row)
        db.flush()
    row.consecutive_failures += 1
    just_blocked = False
    if row.consecutive_failures >= settings.login_max_attempts:
        row.blocked_until = _now() + timedelta(minutes=settings.login_lockout_minutes)
        just_blocked = True
    return LoginFailureOutcome(
        consecutive_failures=int(row.consecutive_failures),
        just_blocked=just_blocked,
    )


def reset_login_failures(db: Session, credential_id: int) -> None:
    row = db.get(LoginAttempt, credential_id)
    if row:
        row.consecutive_failures = 0
        row.blocked_until = None
