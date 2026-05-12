"""Persistencia e invalidación de refresh tokens (JTI)."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.refresh_session import RefreshSession


def persist_refresh_session(db: Session, credential_id: int, jti: UUID, expires_at: datetime) -> RefreshSession:
    row = RefreshSession(
        credential_id=credential_id,
        jti=jti,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        revoked_at=None,
    )
    db.add(row)
    return row


def revoke_refresh_jti(db: Session, jti: UUID) -> None:
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.jti == jti, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


def revoke_all_refresh_for_credential(db: Session, credential_id: int) -> None:
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.credential_id == credential_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


def get_active_refresh_session(db: Session, credential_id: int, jti: UUID) -> RefreshSession | None:
    now = datetime.now(timezone.utc)
    return db.execute(
        select(RefreshSession).where(
            RefreshSession.credential_id == credential_id,
            RefreshSession.jti == jti,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > now,
        )
    ).scalar_one_or_none()
