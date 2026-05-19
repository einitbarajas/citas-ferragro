"""Restablece la contraseña del usuario Admin por documento (solo mantenimiento)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.password_reset_state import PasswordResetState
from app.models.user import User

ADMIN_DOCUMENT_ID = "90000001"
DEFAULT_ADMIN_PASSWORD = "FerragroAdmin2026!"


def reset_admin_password(db: Session, *, password: str = DEFAULT_ADMIN_PASSWORD) -> str:
    """Devuelve el correo del admin tras actualizar la clave."""
    user = db.execute(select(User).where(User.document_id == ADMIN_DOCUMENT_ID)).scalar_one_or_none()
    if not user or not user.credential:
        raise ValueError(f"No existe usuario Admin con documento {ADMIN_DOCUMENT_ID}.")

    cred = user.credential
    cred.password_hash = get_password_hash(password)
    state = db.get(PasswordResetState, cred.id)
    if state:
        db.delete(state)
    db.flush()
    return cred.email
