"""Asegura el Admin de producción (correo/clave válidos, sin bloqueo de login)."""
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.credential import Credential
from app.models.password_reset_state import PasswordResetState
from app.models.provider import Provider
from app.models.role import Role
from app.models.user import User, UserRole
from app.services.credential_cleanup import delete_credential_fully
from app.services.login_policy import reset_login_failures

logger = logging.getLogger(__name__)

ADMIN_DOCUMENT_ID = "90000001"
ADMIN_FULL_NAME = "Administrador Portal"


def _purge_cred_if_orphan(db: Session, credential_id: int) -> None:
    has_user = db.execute(select(User).where(User.credential_id == credential_id)).scalar_one_or_none()
    has_provider = db.execute(select(Provider).where(Provider.credential_id == credential_id)).scalar_one_or_none()
    if has_user or has_provider:
        return
    delete_credential_fully(db, credential_id)


def ensure_production_admin(db: Session) -> bool:
    """
    En producción: crea o corrige el Admin (documento 90000001) si falta o la clave no valida.
    Devuelve True si hubo cambios persistibles.
    """
    if not settings.is_production or not settings.admin_bootstrap_enabled:
        return False

    email = settings.admin_bootstrap_email.strip().lower()
    password = settings.admin_bootstrap_password
    if not email or not password:
        return False

    role_admin = db.execute(select(Role).where(Role.name == UserRole.admin)).scalar_one_or_none()
    if not role_admin:
        logger.warning("admin_bootstrap: no existe rol Admin en la BD")
        return False

    changed = False
    target_cred = db.execute(
        select(Credential).where(func.lower(Credential.email) == email)
    ).scalar_one_or_none()

    if target_cred is None:
        target_cred = Credential(email=email, password_hash=get_password_hash(password))
        db.add(target_cred)
        db.flush()
        changed = True
    else:
        if not verify_password(password, target_cred.password_hash):
            target_cred.password_hash = get_password_hash(password)
            changed = True
        if target_cred.email.strip().lower() != email:
            target_cred.email = email
            changed = True

    for other in db.execute(
        select(User).where(User.credential_id == target_cred.id, User.document_id != ADMIN_DOCUMENT_ID)
    ).scalars():
        db.delete(other)
        changed = True
    db.flush()

    user = db.execute(select(User).where(User.document_id == ADMIN_DOCUMENT_ID)).scalar_one_or_none()
    if user is None:
        db.add(
            User(
                document_id=ADMIN_DOCUMENT_ID,
                full_name=ADMIN_FULL_NAME,
                credential_id=target_cred.id,
                role_id=role_admin.id,
            )
        )
        logger.info("admin_bootstrap: Admin creado (%s)", email)
        return True

    old_cred_id = user.credential_id
    if user.credential_id != target_cred.id:
        user.credential_id = target_cred.id
        changed = True
    if user.role_id != role_admin.id:
        user.role_id = role_admin.id
        changed = True
    if user.full_name != ADMIN_FULL_NAME:
        user.full_name = ADMIN_FULL_NAME
        changed = True

    if old_cred_id != target_cred.id:
        _purge_cred_if_orphan(db, old_cred_id)

    reset_login_failures(db, target_cred.id)
    state = db.get(PasswordResetState, target_cred.id)
    if state:
        db.delete(state)
        changed = True

    attempt_cleared = _clear_block_if_needed(db, target_cred.id)
    if changed:
        logger.info("admin_bootstrap: Admin actualizado (%s)", email)
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
