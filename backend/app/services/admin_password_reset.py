"""Restablece la contraseña del usuario Admin por documento (solo mantenimiento)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.password_reset_state import PasswordResetState
from app.models.user import User
from app.services.credential_cleanup import release_email_for_reuse
from app.services.login_policy import reset_login_failures

ADMIN_DOCUMENT_ID = "90000001"


def reset_admin_password(
    db: Session,
    *,
    password: str | None = None,
    email: str | None = None,
) -> str:
    """Devuelve el correo del admin tras actualizar clave y/o correo."""
    plain = password or settings.admin_bootstrap_password
    target_email = (email or settings.admin_bootstrap_email).strip()

    user = db.execute(select(User).where(User.document_id == ADMIN_DOCUMENT_ID)).scalar_one_or_none()
    if not user or not user.credential:
        raise ValueError(f"No existe usuario Admin con documento {ADMIN_DOCUMENT_ID}.")

    cred = user.credential
    if target_email and cred.email.strip().lower() != target_email.lower():
        release_email_for_reuse(db, target_email, exclude_credential_id=cred.id)
        cred.email = target_email

    cred.password_hash = get_password_hash(plain)
    state = db.get(PasswordResetState, cred.id)
    if state:
        db.delete(state)
    reset_login_failures(db, cred.id)
    db.flush()
    return cred.email
