from datetime import timedelta
import secrets
import string
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import SecurityPrincipal, get_db, get_security_principal
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.responses import ok_response
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password
from app.models.credential import Credential
from app.models.login_audit import LoginAudit
from app.models.provider import Provider
from app.models.password_reset_state import PasswordResetState
from app.models.role import Role
from app.models.user import User, UserRole
from app.schemas.auth import ChangePasswordRequest, ForgotPasswordRequest, LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserOut
from app.services.auth_sessions import (
    get_active_refresh_session,
    persist_refresh_session,
    revoke_all_refresh_for_credential,
    revoke_refresh_jti,
)
from app.services.login_policy import is_login_blocked, record_login_failure, reset_login_failures
from app.services.mailer import send_temporary_password_email, send_welcome_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _generate_temporary_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%*?"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


def _credential_id_for_subject(db: Session, subject: str, role_name: str) -> int | None:
    if role_name == "Proveedor":
        try:
            nit = int(subject)
        except ValueError:
            return None
        prov = db.get(Provider, nit)
        return int(prov.credential_id) if prov else None
    user = db.get(User, subject)
    return int(user.credential_id) if user else None


def _audit_login(
    db: Session,
    *,
    credential_id: int | None,
    email: str,
    success: bool,
    ip: str | None,
    user_agent: str | None,
    failure_reason: str | None = None,
) -> None:
    from datetime import datetime, timezone

    db.add(
        LoginAudit(
            credential_id=credential_id,
            email=email[:255],
            success=success,
            ip_address=ip,
            user_agent=user_agent,
            failure_reason=failure_reason[:255] if failure_reason else None,
            created_at=datetime.now(timezone.utc),
        )
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    cookie_secure = settings.refresh_cookie_secure or settings.is_production
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        httponly=True,
        secure=cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        max_age=int(timedelta(days=settings.refresh_token_expire_days).total_seconds()),
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    cookie_secure = settings.refresh_cookie_secure or settings.is_production
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/",
        secure=cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )


@router.post("/register")
@limiter.limit(f"{settings.rate_limit_per_minute_auth}/minute")
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    exists_cred = db.execute(select(Credential).where(Credential.email == str(payload.email))).scalar_one_or_none()
    if exists_cred:
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    role = db.execute(select(Role).where(Role.name == payload.role_name)).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=400, detail="El rol indicado no existe")

    cred = Credential(email=str(payload.email), password_hash=get_password_hash(payload.password))
    db.add(cred)
    db.flush()

    if payload.role_name == UserRole.proveedor:
        if not payload.digito_verificacion or not payload.documento_persona_responsable or not payload.nombre_persona_responsable:
            raise HTTPException(
                status_code=400,
                detail="Para proveedor debes enviar dígito de verificación, nombre y documento de persona responsable.",
            )
        if not payload.digito_verificacion.isdigit() or len(payload.digito_verificacion) != 1:
            raise HTTPException(status_code=400, detail="El dígito de verificación debe tener exactamente 1 dígito numérico.")
        if not payload.documento_persona_responsable.isdigit() or not (7 <= len(payload.documento_persona_responsable) <= 10):
            raise HTTPException(status_code=400, detail="El documento de la persona responsable debe tener entre 7 y 10 dígitos.")
        if not payload.document_id.isdigit() or len(payload.document_id) != 10:
            raise HTTPException(status_code=400, detail="El NIT debe tener exactamente 10 dígitos numéricos.")
        nit = int(payload.document_id)
        if db.get(Provider, nit):
            raise HTTPException(status_code=400, detail="El NIT ya está registrado")
        provider = Provider(
            nit=nit,
            verification_digit=payload.digito_verificacion,
            company_name=payload.full_name,
            company_email=str(payload.email),
            credential_id=cred.id,
            contact_name=payload.nombre_persona_responsable,
            contact_document=payload.documento_persona_responsable,
        )
        db.add(provider)
        db.commit()
        try:
            send_welcome_email(str(payload.email), payload.full_name)
        except Exception:
            # No bloquea el registro si falla SMTP.
            pass
        return ok_response(
            {
                "document_id": payload.document_id,
                "email": str(payload.email),
                "full_name": payload.full_name,
                "role_name": UserRole.proveedor,
            },
            "Proveedor registrado correctamente",
        )

    if payload.role_name != UserRole.logistica:
        raise HTTPException(
            status_code=400,
            detail="El registro público solo está habilitado para Proveedor o Logistica",
        )

    user = User(
        document_id=payload.document_id,
        full_name=payload.full_name,
        credential_id=cred.id,
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    try:
        send_welcome_email(str(payload.email), payload.full_name)
    except Exception:
        # No bloquea el registro si falla SMTP.
        pass
    db.refresh(user)
    user_out = UserOut(
        document_id=user.document_id,
        email=user.credential.email,
        full_name=user.full_name,
        role_name=user.role.name,
    )
    return ok_response(user_out.model_dump(), "Usuario registrado correctamente")


def _issue_tokens(response: Response, db: Session, credential_id: int, subject: str, role_name: str):
    from datetime import datetime, timezone

    access_token = create_access_token(subject=subject, role=role_name)
    refresh_token_str, jti = create_refresh_token(subject=subject, role=role_name)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    persist_refresh_session(db, credential_id, jti, expires_at)
    _set_refresh_cookie(response, refresh_token_str)
    reset_state = db.get(PasswordResetState, credential_id)
    token_out = TokenResponse(
        access_token=access_token,
        role=role_name,
        must_change_password=bool(reset_state and reset_state.must_change_password),
    )
    return ok_response(token_out.model_dump(), "Inicio de sesión exitoso")


@router.post("/login")
@limiter.limit(f"{settings.rate_limit_per_minute_auth}/minute")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip()
    ip = _client_ip(request)
    ua = request.headers.get("user-agent")

    cred = db.execute(select(Credential).where(Credential.email == email)).scalar_one_or_none()
    if not cred:
        _audit_login(db, credential_id=None, email=email, success=False, ip=ip, user_agent=ua, failure_reason="correo_no_registrado")
        db.commit()
        raise HTTPException(status_code=401, detail="Email o contraseña inválidos")

    blocked, _until = is_login_blocked(db, cred.id)
    if blocked:
        _audit_login(db, credential_id=cred.id, email=email, success=False, ip=ip, user_agent=ua, failure_reason="cuenta_bloqueada")
        db.commit()
        raise HTTPException(
            status_code=429,
            detail=f"Cuenta temporalmente bloqueada. Intenta de nuevo en {settings.login_lockout_minutes} minutos.",
        )

    if not verify_password(payload.password, cred.password_hash):
        record_login_failure(db, cred.id)
        _audit_login(db, credential_id=cred.id, email=email, success=False, ip=ip, user_agent=ua, failure_reason="clave_incorrecta")
        db.commit()
        raise HTTPException(status_code=401, detail="Email o contraseña inválidos")

    reset_login_failures(db, cred.id)

    user = db.execute(select(User).where(User.credential_id == cred.id)).scalar_one_or_none()
    if user:
        role_name = user.role.name if user.role else ""
        access_token = create_access_token(subject=str(user.document_id), role=role_name)
        refresh_token_str, jti = create_refresh_token(subject=str(user.document_id), role=role_name)
        from datetime import datetime, timezone

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
        persist_refresh_session(db, cred.id, jti, expires_at)
        _set_refresh_cookie(response, refresh_token_str)
        _audit_login(db, credential_id=cred.id, email=email, success=True, ip=ip, user_agent=ua)
        db.commit()
        reset_state = db.get(PasswordResetState, cred.id)
        token_out = TokenResponse(
            access_token=access_token,
            role=role_name,
            must_change_password=bool(reset_state and reset_state.must_change_password),
        )
        return ok_response(token_out.model_dump(), "Inicio de sesión exitoso")

    provider = db.execute(select(Provider).where(Provider.credential_id == cred.id)).scalar_one_or_none()
    if provider:
        role_name = "Proveedor"
        subject = str(int(provider.nit))
        access_token = create_access_token(subject=subject, role=role_name)
        refresh_token_str, jti = create_refresh_token(subject=subject, role=role_name)
        from datetime import datetime, timezone

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
        persist_refresh_session(db, cred.id, jti, expires_at)
        _set_refresh_cookie(response, refresh_token_str)
        _audit_login(db, credential_id=cred.id, email=email, success=True, ip=ip, user_agent=ua)
        db.commit()
        reset_state = db.get(PasswordResetState, cred.id)
        token_out = TokenResponse(
            access_token=access_token,
            role=role_name,
            must_change_password=bool(reset_state and reset_state.must_change_password),
        )
        return ok_response(token_out.model_dump(), "Inicio de sesión exitoso")

    _audit_login(db, credential_id=cred.id, email=email, success=False, ip=ip, user_agent=ua, failure_reason="cuenta_sin_actor")
    db.commit()
    raise HTTPException(status_code=401, detail="Email o contraseña inválidos")


@router.post("/refresh")
@limiter.limit(f"{settings.rate_limit_per_minute_auth}/minute")
def refresh_access_token(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No hay sesión para refrescar")
    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])
        subject = str(payload.get("sub") or "")
        role_name = str(payload.get("role") or "")
        token_type = str(payload.get("token_type") or "")
        jti_raw = str(payload.get("jti") or "")
        if not subject or not role_name or token_type != "refresh" or not jti_raw:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")
        jti = UUID(jti_raw)
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")

    cred_id = _credential_id_for_subject(db, subject, role_name)
    if cred_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")

    session_row = get_active_refresh_session(db, cred_id, jti)
    if not session_row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión revocada o expirada")

    revoke_refresh_jti(db, jti)
    new_access = create_access_token(subject=subject, role=role_name)
    new_refresh_str, new_jti = create_refresh_token(subject=subject, role=role_name)
    from datetime import datetime, timezone

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    persist_refresh_session(db, cred_id, new_jti, expires_at)
    _set_refresh_cookie(response, new_refresh_str)
    reset_state = db.get(PasswordResetState, cred_id)
    token_out = TokenResponse(
        access_token=new_access,
        role=role_name,
        must_change_password=bool(reset_state and reset_state.must_change_password),
    )
    db.commit()
    return ok_response(token_out.model_dump(), "Token renovado")


@router.post("/forgot-password")
@limiter.limit(f"{settings.rate_limit_per_minute_auth}/minute")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    email = str(payload.email).strip()
    cred = db.execute(select(Credential).where(Credential.email == email)).scalar_one_or_none()
    if not cred:
        # Respuesta genérica para no filtrar qué correos existen.
        return ok_response(None, "Si el correo existe, se enviará una contraseña temporal.")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    state = db.get(PasswordResetState, cred.id)
    if state and state.temporary_issued_at:
        elapsed = (now - state.temporary_issued_at).total_seconds()
        cooldown = max(1, int(settings.forgot_password_cooldown_seconds))
        if elapsed < cooldown:
            remaining = int(cooldown - elapsed)
            raise HTTPException(
                status_code=429,
                detail=f"Ya solicitaste una contraseña temporal. Espera {remaining} segundos para solicitar otra.",
                headers={"Retry-After": str(remaining)},
            )

    temporary_password = _generate_temporary_password()
    cred.password_hash = get_password_hash(temporary_password)

    if not state:
        state = PasswordResetState(credential_id=cred.id, must_change_password=True, temporary_issued_at=now)
        db.add(state)
    else:
        state.must_change_password = True
        state.temporary_issued_at = now

    try:
        send_temporary_password_email(email, temporary_password)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible enviar el correo de recuperación.")

    db.commit()
    return ok_response(None, "Si el correo existe, se enviará una contraseña temporal.")


@router.post("/change-password")
@limiter.limit(f"{settings.rate_limit_per_minute_auth}/minute")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    cred_id = principal.user.credential_id if principal.user else None
    if cred_id is None and principal.provider:
        cred_id = principal.provider.credential_id
    if cred_id is None:
        raise HTTPException(status_code=400, detail="No se pudo resolver la credencial.")

    cred = db.get(Credential, cred_id)
    if not cred:
        raise HTTPException(status_code=404, detail="Credencial no encontrada.")
    if not verify_password(payload.current_password, cred.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual no es válida.")
    if len(payload.new_password or "") < 8:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 8 caracteres.")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser diferente a la actual.")

    cred.password_hash = get_password_hash(payload.new_password)
    state = db.get(PasswordResetState, cred_id)
    if not state:
        state = PasswordResetState(credential_id=cred_id, must_change_password=False, temporary_issued_at=None)
        db.add(state)
    else:
        state.must_change_password = False
        state.temporary_issued_at = None

    db.commit()
    return ok_response(None, "Contraseña actualizada correctamente.")


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])
            subject = str(payload.get("sub") or "")
            role_name = str(payload.get("role") or "")
            jti_raw = str(payload.get("jti") or "")
            if jti_raw and subject and role_name:
                jti = UUID(jti_raw)
                cred_id = _credential_id_for_subject(db, subject, role_name)
                if cred_id is not None:
                    revoke_refresh_jti(db, jti)
        except (JWTError, ValueError, TypeError):
            pass
    _clear_refresh_cookie(response)
    db.commit()
    return ok_response(None, "Sesión cerrada")


@router.post("/logout-all-devices")
def logout_all_devices(
    response: Response,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    """Invalida todos los refresh tokens del usuario autenticado."""
    cred_id = principal.user.credential_id if principal.user else None
    if cred_id is None and principal.provider:
        cred_id = principal.provider.credential_id
    if cred_id is None:
        raise HTTPException(status_code=400, detail="No se pudo resolver la credencial")
    revoke_all_refresh_for_credential(db, cred_id)
    _clear_refresh_cookie(response)
    db.commit()
    return ok_response(None, "Sesiones cerradas en todos los dispositivos")
