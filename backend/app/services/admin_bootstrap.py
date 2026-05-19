"""Asegura el Admin de producción (correo/clave válidos, sin bloqueo de login)."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.credential import Credential
from app.models.password_reset_state import PasswordResetState
from app.models.role import Role
from app.models.user import User, UserRole
from app.services.credential_cleanup import release_email_for_reuse
from app.services.login_policy import reset_login_failures

logger = logging.getLogger(__name__)

ADMIN_DOCUMENT_ID = "90000001"
ADMIN_FULL_NAME = "Administrador Portal"


def ensure_production_admin(db: Session) -> bool:
    """
    En producción: crea o corrige el Admin (documento 90000001) si falta o la clave no valida.
    Devuelve True si hubo cambios persistibles.
    """
    if not settings.is_production or not settings.admin_bootstrap_enabled:
        return False

    email = settings.admin_bootstrap_email.strip()
    password = settings.admin_bootstrap_password
    if not email or not password:
        return False

    role_admin = db.execute(select(Role).where(Role.name == UserRole.admin)).scalar_one_or_none()
    if not role_admin:
        logger.warning("admin_bootstrap: no existe rol Admin en la BD")
        return False

    changed = False
    user = db.execute(select(User).where(User.document_id == ADMIN_DOCUMENT_ID)).scalar_one_or_none()

    if user is None:
        release_email_for_reuse(db, email)
        cred = Credential(email=email, password_hash=get_password_hash(password))
        db.add(cred)
        db.flush()
        db.add(
            User(
                document_id=ADMIN_DOCUMENT_ID,
                full_name=ADMIN_FULL_NAME,
                credential_id=cred.id,
                role_id=role_admin.id,
            )
        )
        logger.info("admin_bootstrap: Admin creado (%s)", email)
        return True

    cred = user.credential
    if cred is None:
        logger.error("admin_bootstrap: usuario %s sin credencial", ADMIN_DOCUMENT_ID)
        return False

    if cred.email.strip().lower() != email.lower():
        release_email_for_reuse(db, email, exclude_credential_id=cred.id)
        cred.email = email
        changed = True

    if not verify_password(password, cred.password_hash):
        cred.password_hash = get_password_hash(password)
        changed = True
        logger.info("admin_bootstrap: contraseña del Admin actualizada (%s)", email)

    reset_login_failures(db, cred.id)
    state = db.get(PasswordResetState, cred.id)
    if state:
        db.delete(state)
        changed = True

    attempt_cleared = _clear_block_if_needed(db, cred.id)
    return changed or attempt_cleared


def _clear_block_if_needed(db: Session, credential_id: int) -> bool:
    from app.models.login_attempt import LoginAttempt

    row = db.get(LoginAttempt, credential_id)
    if not row:
        return False
    if row.blocked_until or (row.consecutive_failures or 0) > 0:
        reset_login_failures(db, credential_id)
        return True
    return False
