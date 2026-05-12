from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.provider import Provider
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass
class SecurityPrincipal:
    """Usuario interno o proveedor autenticado vía JWT (mismo login por correo)."""

    subject: str
    role_name: str
    user: Optional[User] = None
    provider: Optional[Provider] = None

    @property
    def document_id(self) -> str:
        return self.subject

    @property
    def role(self):
        class _Role:
            __slots__ = ("name",)

            def __init__(self, name: str) -> None:
                self.name = name

        return _Role(self.role_name)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_security_principal(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> SecurityPrincipal:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        subject = str(payload.get("sub") or "")
        role_name = str(payload.get("role") or "")
        token_type = str(payload.get("token_type") or "")
        exp = payload.get("exp")
        if not subject or not role_name:
            raise credentials_exception
        if token_type and token_type != "access":
            raise credentials_exception
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise credentials_exception
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    if role_name == "Proveedor":
        try:
            nit = int(subject)
        except ValueError:
            raise credentials_exception
        provider = db.get(Provider, nit)
        if not provider:
            raise credentials_exception
        return SecurityPrincipal(subject=str(nit), role_name=role_name, provider=provider)

    user = db.get(User, subject)
    if not user:
        raise credentials_exception
    actual = user.role.name if user.role else ""
    if actual != role_name:
        raise credentials_exception
    return SecurityPrincipal(subject=subject, role_name=actual, user=user)


def get_current_user(principal: SecurityPrincipal = Depends(get_security_principal)) -> User:
    if principal.user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere usuario interno")
    return principal.user


def require_roles(*allowed_roles: str):
    def checker(principal: SecurityPrincipal = Depends(get_security_principal)) -> SecurityPrincipal:
        if principal.role_name not in allowed_roles:
            raise HTTPException(status_code=403, detail="No autorizado para este recurso")
        return principal

    return checker
