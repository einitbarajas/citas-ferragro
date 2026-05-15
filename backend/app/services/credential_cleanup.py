from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.credential import Credential
from app.models.login_attempt import LoginAttempt
from app.models.login_audit import LoginAudit
from app.models.password_reset_state import PasswordResetState
from app.models.profile_photo import ProfilePhoto
from app.models.provider import Provider
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.services.auth_sessions import revoke_all_refresh_for_credential


def credential_has_active_owner(db: Session, credential_id: int) -> bool:
    user = db.execute(select(User).where(User.credential_id == credential_id)).scalar_one_or_none()
    if user:
        return True
    provider = db.execute(select(Provider).where(Provider.credential_id == credential_id)).scalar_one_or_none()
    return provider is not None


def purge_credential_dependencies(db: Session, credential_id: int) -> None:
    db.execute(delete(ProfilePhoto).where(ProfilePhoto.credential_id == credential_id))
    db.execute(delete(LoginAudit).where(LoginAudit.credential_id == credential_id))
    revoke_all_refresh_for_credential(db, credential_id)
    db.execute(delete(RefreshSession).where(RefreshSession.credential_id == credential_id))
    attempt = db.get(LoginAttempt, credential_id)
    if attempt:
        db.delete(attempt)
    reset = db.get(PasswordResetState, credential_id)
    if reset:
        db.delete(reset)


def delete_credential_fully(db: Session, credential_id: int) -> None:
    purge_credential_dependencies(db, credential_id)
    cred = db.get(Credential, credential_id)
    if cred:
        db.delete(cred)


def release_email_for_reuse(db: Session, email: str, *, exclude_credential_id: int | None = None) -> list[int]:
    """Elimina credenciales huérfanas con ese correo. Devuelve ids eliminados."""
    normalized = email.strip().lower()
    query = select(Credential).where(func.lower(Credential.email) == normalized)
    if exclude_credential_id is not None:
        query = query.where(Credential.id != exclude_credential_id)
    removed: list[int] = []
    for cred in db.execute(query).scalars().all():
        if credential_has_active_owner(db, cred.id):
            raise HTTPException(status_code=400, detail="El email ya está registrado")
        delete_credential_fully(db, cred.id)
        removed.append(cred.id)
    return removed
