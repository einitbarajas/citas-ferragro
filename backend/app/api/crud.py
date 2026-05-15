from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import Date, cast, extract, func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import SecurityPrincipal, get_db, get_security_principal, require_roles
from app.core.config import settings
from app.core.responses import ok_response
from app.core.security import get_password_hash, verify_password
from app.models.appointment import Appointment, AppointmentStatus
from app.models.admin_event import AdminEvent
from app.models.audit_log import ChangeLog
from app.models.appointment_date_window import AppointmentDateWindow
from app.models.credential import Credential
from app.models.provider import Provider
from app.models.profile_photo import ProfilePhoto
from app.models.reminder_run import ReminderExecution
from app.models.role import Role
from app.models.user import User
from app.services.notification_service import notify_provider_appointment_updated, notify_staff_review_needed
from app.schemas.crud import (
    AppointmentDateWindowReplace,
    AppointmentDateWindowBulkReplace,
    AnalyticsSummaryOut,
    AppointmentCrudOut,
    AppointmentIn,
    AppointmentUpdate,
    AppointmentWindowOut,
    AppointmentWindowsReplace,
    ChangeLogIn,
    ChangeLogOut,
    ChangeLogUpdate,
    ProviderIn,
    ProviderOut,
    ProviderUpdate,
    ProfileMeOut,
    ProfileMeUpdate,
    ProfilePasswordChange,
    RoleIn,
    RoleOut,
    UserCrudOut,
    UserIn,
    UserUpdate,
)
from app.services.cloudinary_service import upload_profile_photo
from app.services.appointment_windows import (
    clear_date_windows,
    assert_start_within_windows,
    format_schedule_hint,
    list_date_windows_ordered,
    replace_date_windows,
    list_windows_ordered,
    replace_windows,
)
from app.services.appointment_service import finalize_elapsed_appointments, reserve_slot_fifo_or_raise
from app.services.range_bounds import business_local_range_bounds

router = APIRouter(prefix="/crud", tags=["crud"])


def _local_day_utc_bounds(target_day: date) -> tuple[datetime, datetime]:
    tz = ZoneInfo(settings.business_timezone)
    local_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def _appointments_count_on_local_day(db: Session, target_day: date) -> int:
    start_utc, end_utc = _local_day_utc_bounds(target_day)
    return int(
        db.execute(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.start_time >= start_utc,
                Appointment.start_time < end_utc,
                Appointment.status.not_in(
                    (
                        AppointmentStatus.cancelado,
                        AppointmentStatus.finalizada,
                        AppointmentStatus.no_presentada,
                    )
                ),
            )
        ).scalar_one()
        or 0
    )


def _assert_non_overlapping_windows(parsed: list[tuple], error_prefix: str = "Franja inválida") -> None:
    prev_end = None
    for idx, (hi, hf) in enumerate(parsed, start=1):
        if hf <= hi:
            raise HTTPException(status_code=400, detail="En cada franja la hora fin debe ser mayor que la de inicio")
        if prev_end is not None and hi <= prev_end:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{error_prefix}: la franja #{idx} debe iniciar después de la franja anterior "
                    f"(actual {hi.strftime('%H:%M')}, anterior termina {prev_end.strftime('%H:%M')})."
                ),
            )
        prev_end = hf


def _parse_and_validate_windows(items: list, error_prefix: str) -> list[tuple]:
    parsed: list[tuple] = []
    for w in items:
        hi = datetime.strptime(w.start_local, "%H:%M").time()
        hf = datetime.strptime(w.end_local, "%H:%M").time()
        parsed.append((hi, hf))
    parsed.sort(key=lambda x: (x[0].hour, x[0].minute))
    _assert_non_overlapping_windows(parsed, error_prefix)
    return parsed


def _time_allowed_in_windows(local_time, windows: list[tuple]) -> bool:
    local_minutes = local_time.hour * 60 + local_time.minute
    for start_local, end_local in windows:
        if not (start_local <= local_time <= end_local):
            continue
        window_start_minutes = start_local.hour * 60 + start_local.minute
        if (local_minutes - window_start_minutes) % 90 == 0:
            return True
    return False


def _assert_weekly_windows_do_not_break_existing_appointments(db: Session, weekly_windows: list[tuple]) -> None:
    tz = ZoneInfo(settings.business_timezone)
    local_today = datetime.now(tz).date()
    start_utc, _ = _local_day_utc_bounds(local_today)
    appointments = (
        db.execute(
            select(Appointment.start_time)
            .where(
                Appointment.status != AppointmentStatus.cancelado,
                Appointment.start_time >= start_utc,
            )
            .order_by(Appointment.start_time.asc())
        )
        .scalars()
        .all()
    )
    if not appointments:
        return

    override_days = set(
        db.execute(
            select(AppointmentDateWindow.day)
            .where(AppointmentDateWindow.day >= local_today)
            .group_by(AppointmentDateWindow.day)
        )
        .scalars()
        .all()
    )

    conflicts: list[str] = []
    for start_time in appointments:
        aware_start = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        local_dt = aware_start.astimezone(tz)
        if local_dt.date() in override_days:
            continue
        if not _time_allowed_in_windows(local_dt.time(), weekly_windows):
            conflicts.append(local_dt.strftime("%Y-%m-%d %H:%M"))

    if conflicts:
        examples = ", ".join(conflicts[:3])
        suffix = "..." if len(conflicts) > 3 else ""
        raise HTTPException(
            status_code=409,
            detail=(
                "No se pueden guardar estas franjas porque dejarían citas existentes fuera de horario "
                f"(ej.: {examples}{suffix}). Ajusta las franjas sin excluir horarios con citas."
            ),
        )


def _appointment_to_crud_out(appt: Appointment) -> dict:
    pname = appt.provider.company_name if appt.provider else ""
    return AppointmentCrudOut(
        id=appt.id,
        provider_id=int(appt.provider_id),
        provider_name=pname,
        material_description=appt.material_description,
        start_time=appt.start_time,
        duration_minutes=appt.duration_minutes,
        status=appt.status,
    ).model_dump()


def _user_to_out(user: User) -> UserCrudOut:
    email = user.credential.email if user.credential else ""
    return UserCrudOut(
        document_id=user.document_id,
        email=email,
        full_name=user.full_name,
        role_id=user.role_id,
        role_name=user.role.name if user.role else "",
    )


def _actor_display(db: Session, actor_id: str) -> tuple[str, str]:
    user = db.get(User, actor_id)
    if user and user.role:
        return (user.full_name or "", user.role.name or "")
    try:
        nit = int(actor_id)
    except ValueError:
        return ("", "")
    prov = db.get(Provider, nit)
    if prov:
        return (prov.company_name or "", "Proveedor")
    return ("", "")


def _change_log_to_out(db: Session, log: ChangeLog) -> dict:
    name, role = _actor_display(db, log.actor_id)
    return ChangeLogOut(
        id=log.id,
        actor_id=log.actor_id,
        appointment_id=log.appointment_id,
        action=log.action,
        description=log.description,
        created_at=log.created_at,
        actor_name=name,
        actor_role=role,
        critical_field=log.critical_field,
        old_value=log.old_value,
        new_value=log.new_value,
    ).model_dump()


def _admin_event_to_out(db: Session, event: AdminEvent) -> dict:
    name, role = _actor_display(db, event.actor_id)
    return ChangeLogOut(
        id=event.id,
        actor_id=event.actor_id,
        appointment_id=None,
        action=event.action,
        description=event.description,
        created_at=event.created_at,
        actor_name=name,
        actor_role=role,
    ).model_dump()


def _log_admin_event(db: Session, actor_id: str, action: str, description: str, target_document_id: str | None) -> None:
    db.add(
        AdminEvent(
            actor_id=actor_id,
            action=action,
            description=description,
            created_at=datetime.now(timezone.utc),
            target_document_id=target_document_id,
        )
    )


def _resolve_principal_entities(
    principal,
    db: Session,
) -> tuple[str, str, Credential, ProfilePhoto | None]:
    if principal.user is not None:
        role_name = principal.user.role.name if principal.user.role else principal.role_name
        cred = principal.user.credential
        if not cred:
            raise HTTPException(status_code=500, detail="Usuario sin credenciales asociadas")
        photo = db.execute(select(ProfilePhoto).where(ProfilePhoto.credential_id == cred.id)).scalar_one_or_none()
        return principal.user.document_id, role_name, cred, photo
    if principal.provider is not None:
        cred = principal.provider.credential
        if not cred:
            raise HTTPException(status_code=500, detail="Proveedor sin credenciales asociadas")
        photo = db.execute(select(ProfilePhoto).where(ProfilePhoto.credential_id == cred.id)).scalar_one_or_none()
        return str(int(principal.provider.nit)), "Proveedor", cred, photo
    raise HTTPException(status_code=401, detail="Credenciales inválidas")


@router.get("/roles", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def list_roles(db: Session = Depends(get_db)):
    roles = db.execute(select(Role).order_by(Role.id.asc())).scalars().all()
    data = [RoleOut.model_validate(role).model_dump() for role in roles]
    return ok_response(data, "Roles consultados correctamente")


@router.post("/roles", dependencies=[Depends(require_roles("Admin"))])
def create_role(payload: RoleIn, db: Session = Depends(get_db)):
    role = Role(name=payload.name)
    db.add(role)
    db.commit()
    db.refresh(role)
    return ok_response(RoleOut.model_validate(role).model_dump(), "Rol creado correctamente")


@router.put("/roles/{role_id}", dependencies=[Depends(require_roles("Admin"))])
def update_role(role_id: int, payload: RoleIn, db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    role.name = payload.name
    db.commit()
    db.refresh(role)
    return ok_response(RoleOut.model_validate(role).model_dump(), "Rol actualizado correctamente")


@router.delete("/roles/{role_id}", dependencies=[Depends(require_roles("Admin"))])
def delete_role(role_id: int, db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    db.delete(role)
    db.commit()
    return ok_response(None, "Rol eliminado correctamente")


@router.get("/users", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def list_users(db: Session = Depends(get_db)):
    users = (
        db.execute(
            select(User)
            .options(joinedload(User.role), joinedload(User.credential))
            .order_by(User.full_name.asc())
        )
        .scalars()
        .all()
    )
    data = [_user_to_out(user).model_dump() for user in users]
    return ok_response(data, "Usuarios consultados correctamente")


@router.get("/users/{document_id}", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def get_user(document_id: str, db: Session = Depends(get_db)):
    user = db.get(User, document_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return ok_response(_user_to_out(user).model_dump(), "Usuario consultado correctamente")


@router.post("/users", dependencies=[Depends(require_roles("Admin"))])
def create_user(
    payload: UserIn,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    role = db.get(Role, payload.role_id)
    if not role:
        raise HTTPException(status_code=400, detail="El rol no existe")
    if role.name not in ("Admin", "Logistica"):
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden crear usuarios internos con rol Admin o Logistica",
        )
    if db.get(User, payload.document_id):
        raise HTTPException(status_code=400, detail="El documento ya está registrado")
    if db.execute(select(Credential).where(Credential.email == str(payload.email))).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    cred = Credential(email=str(payload.email), password_hash=get_password_hash(payload.password))
    db.add(cred)
    db.flush()

    user = User(
        document_id=payload.document_id,
        full_name=payload.full_name,
        credential_id=cred.id,
        role_id=payload.role_id,
    )
    db.add(user)
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="user_create",
        description=f"Creó usuario interno {payload.full_name} ({payload.document_id})",
        target_document_id=payload.document_id,
    )
    db.commit()
    db.refresh(user)
    return ok_response(_user_to_out(user).model_dump(), "Usuario creado correctamente")


@router.put("/users/{document_id}", dependencies=[Depends(require_roles("Admin"))])
def update_user(
    document_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    user = db.get(User, document_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    updates = payload.model_dump(exclude_unset=True)
    if "role_id" in updates and not db.get(Role, updates["role_id"]):
        raise HTTPException(status_code=400, detail="El rol no existe")

    cred = user.credential
    if not cred:
        raise HTTPException(status_code=500, detail="Usuario sin credenciales asociadas")

    if "email" in updates:
        new_email = str(updates.pop("email"))
        other = db.execute(select(Credential).where(Credential.email == new_email, Credential.id != cred.id)).scalar_one_or_none()
        if other:
            raise HTTPException(status_code=400, detail="El email ya está registrado")
        cred.email = new_email
    if "password" in updates:
        pwd = updates.pop("password")
        cred.password_hash = get_password_hash(pwd)

    for key, value in updates.items():
        setattr(user, key, value)
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="user_update",
        description=f"Actualizó usuario interno {user.full_name} ({user.document_id})",
        target_document_id=user.document_id,
    )
    db.commit()
    db.refresh(user)
    return ok_response(_user_to_out(user).model_dump(), "Usuario actualizado correctamente")


@router.delete("/users/{document_id}", dependencies=[Depends(require_roles("Admin"))])
def delete_user(
    document_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    user = db.get(User, document_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    cid = user.credential_id
    deleted_name = user.full_name
    db.delete(user)
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="user_delete",
        description=f"Eliminó usuario interno {deleted_name} ({document_id})",
        target_document_id=document_id,
    )
    db.commit()
    cred = db.get(Credential, cid)
    if cred:
        db.delete(cred)
        db.commit()
    return ok_response(None, "Usuario eliminado correctamente")


@router.get("/profile/me", dependencies=[Depends(require_roles("Admin", "Logistica", "Proveedor"))])
def get_my_profile(
    principal: SecurityPrincipal = Depends(get_security_principal),
    db: Session = Depends(get_db),
):
    document_id, role_name, cred, photo = _resolve_principal_entities(principal, db)
    if principal.user is not None:
        full_name = principal.user.full_name
    elif principal.provider is not None:
        full_name = principal.provider.contact_name
    else:
        full_name = ""
    data = ProfileMeOut(
        document_id=document_id,
        role_name=role_name,
        full_name=full_name,
        email=cred.email,
        photo_url=photo.photo_url if photo else None,
    ).model_dump()
    return ok_response(data, "Perfil consultado correctamente")


@router.put("/profile/me", dependencies=[Depends(require_roles("Admin", "Logistica", "Proveedor"))])
def update_my_profile(
    payload: ProfileMeUpdate,
    principal: SecurityPrincipal = Depends(get_security_principal),
    db: Session = Depends(get_db),
):
    _, _, cred, _ = _resolve_principal_entities(principal, db)
    other_cred = db.execute(select(Credential).where(Credential.email == str(payload.email), Credential.id != cred.id)).scalar_one_or_none()
    if other_cred:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    cred.email = str(payload.email)
    if principal.user is not None:
        principal.user.full_name = payload.full_name
    elif principal.provider is not None:
        principal.provider.contact_name = payload.full_name
    db.commit()
    return get_my_profile(principal=principal, db=db)


@router.post("/profile/me/change-password", dependencies=[Depends(require_roles("Admin", "Logistica", "Proveedor"))])
def change_my_password(
    payload: ProfilePasswordChange,
    principal: SecurityPrincipal = Depends(get_security_principal),
    db: Session = Depends(get_db),
):
    _, _, cred, _ = _resolve_principal_entities(principal, db)
    if not verify_password(payload.current_password, cred.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    cred.password_hash = get_password_hash(payload.new_password)
    db.commit()
    return ok_response(None, "Contraseña actualizada correctamente")


@router.post("/profile/me/photo", dependencies=[Depends(require_roles("Admin", "Logistica", "Proveedor"))])
async def upload_my_profile_photo(
    file: UploadFile = File(...),
    principal: SecurityPrincipal = Depends(get_security_principal),
    db: Session = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="La imagen está vacía")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen no puede superar 5MB")
    _, _, cred, photo = _resolve_principal_entities(principal, db)
    safe_filename = (file.filename or "perfil").replace(" ", "_")
    photo_url = upload_profile_photo(raw, safe_filename)
    if photo is None:
        photo = ProfilePhoto(credential_id=cred.id, photo_url=photo_url)
        db.add(photo)
    else:
        photo.photo_url = photo_url
    db.commit()
    return get_my_profile(principal=principal, db=db)


@router.delete("/profile/me/photo", dependencies=[Depends(require_roles("Admin", "Logistica", "Proveedor"))])
def clear_my_profile_photo(
    principal: SecurityPrincipal = Depends(get_security_principal),
    db: Session = Depends(get_db),
):
    _, _, _, photo = _resolve_principal_entities(principal, db)
    if photo:
        photo.photo_url = None
        db.commit()
    return get_my_profile(principal=principal, db=db)


@router.get("/providers", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def list_providers(db: Session = Depends(get_db)):
    providers = db.execute(select(Provider).order_by(Provider.company_name.asc())).scalars().all()
    data = [ProviderOut.model_validate(provider).model_dump() for provider in providers]
    return ok_response(data, "Proveedores consultados correctamente")


@router.get("/providers/{nit}", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def get_provider(nit: int, db: Session = Depends(get_db)):
    provider = db.get(Provider, nit)
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return ok_response(ProviderOut.model_validate(provider).model_dump(), "Proveedor consultado correctamente")


@router.post("/providers", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def create_provider(
    payload: ProviderIn,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    if db.get(Provider, payload.nit):
        raise HTTPException(status_code=400, detail="El NIT ya está registrado")
    if db.execute(select(Credential).where(Credential.email == str(payload.company_email))).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    data = payload.model_dump()
    password = data.pop("password")
    cred = Credential(email=str(payload.company_email), password_hash=get_password_hash(password))
    db.add(cred)
    db.flush()

    provider = Provider(
        nit=data["nit"],
        verification_digit=data["verification_digit"],
        company_name=data["company_name"],
        company_email=str(payload.company_email),
        credential_id=cred.id,
        contact_name=data["contact_name"],
        contact_document=data["contact_document"],
    )
    db.add(provider)
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="provider_create",
        description=f"Creó proveedor {payload.company_name} (NIT {payload.nit})",
        target_document_id=str(payload.nit),
    )
    db.commit()
    db.refresh(provider)
    return ok_response(ProviderOut.model_validate(provider).model_dump(), "Proveedor creado correctamente")


@router.put("/providers/{nit}", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def update_provider(
    nit: int,
    payload: ProviderUpdate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    provider = db.get(Provider, nit)
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    cred = provider.credential
    if not cred:
        raise HTTPException(status_code=500, detail="Proveedor sin credenciales asociadas")

    updates = payload.model_dump(exclude_unset=True)
    if "password" in updates:
        cred.password_hash = get_password_hash(updates.pop("password"))
    if "company_email" in updates:
        new_email = str(updates.pop("company_email"))
        other = db.execute(
            select(Credential).where(Credential.email == new_email, Credential.id != cred.id)
        ).scalar_one_or_none()
        if other:
            raise HTTPException(status_code=400, detail="El email ya está registrado")
        cred.email = new_email
        provider.company_email = new_email

    for key, value in updates.items():
        setattr(provider, key, value)
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="provider_update",
        description=f"Actualizó proveedor {provider.company_name} (NIT {nit})",
        target_document_id=str(nit),
    )
    db.commit()
    db.refresh(provider)
    return ok_response(ProviderOut.model_validate(provider).model_dump(), "Proveedor actualizado correctamente")


@router.delete("/providers/{nit}", dependencies=[Depends(require_roles("Admin"))])
def delete_provider(
    nit: int,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    provider = db.get(Provider, nit)
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    cid = provider.credential_id
    deleted_name = provider.company_name
    db.delete(provider)
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="provider_delete",
        description=f"Eliminó proveedor {deleted_name} (NIT {nit})",
        target_document_id=str(nit),
    )
    db.commit()
    cred = db.get(Credential, cid)
    if cred:
        db.delete(cred)
        db.commit()
    return ok_response(None, "Proveedor eliminado correctamente")


def _staff_appointments_select(
    *,
    mode: str,
    day: date | None,
    month: int | None,
    year: int | None,
    status_list: list[str] | None,
    provider_id: int | None,
    date_from: date | None,
    date_to: date | None,
    sort_by: str,
    sort_dir: str,
):
    stmt = select(Appointment).options(joinedload(Appointment.provider))
    if provider_id is not None:
        stmt = stmt.where(Appointment.provider_id == provider_id)

    if status_list:
        enums = []
        for s in status_list:
            try:
                enums.append(AppointmentStatus(s))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Estado inválido: {s}")
        stmt = stmt.where(Appointment.status.in_(enums))

    if date_from is not None:
        start_d = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
        stmt = stmt.where(Appointment.start_time >= start_d)
    if date_to is not None:
        end_d = datetime(date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc) + timedelta(days=1)
        stmt = stmt.where(Appointment.start_time < end_d)

    if mode == "day" and day:
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        stmt = stmt.where(Appointment.start_time >= start, Appointment.start_time < end)
    elif mode == "week":
        tz = ZoneInfo(settings.business_timezone)
        local_now = datetime.now(tz)
        start_local, end_local = business_local_range_bounds("week", local_now, tz)
        start = start_local.astimezone(timezone.utc)
        end = end_local.astimezone(timezone.utc)
        stmt = stmt.where(Appointment.start_time >= start, Appointment.start_time < end)
    elif mode == "biweekly":
        tz = ZoneInfo(settings.business_timezone)
        local_now = datetime.now(tz)
        start_local, end_local = business_local_range_bounds("biweekly", local_now, tz)
        start = start_local.astimezone(timezone.utc)
        end = end_local.astimezone(timezone.utc)
        stmt = stmt.where(Appointment.start_time >= start, Appointment.start_time < end)
    elif mode == "month" and month and year:
        stmt = stmt.where(
            extract("month", Appointment.start_time) == month,
            extract("year", Appointment.start_time) == year,
        )

    order_col = Appointment.start_time if sort_by == "start_time" else Appointment.id
    stmt = stmt.order_by(order_col.asc() if sort_dir == "asc" else order_col.desc())
    return stmt


@router.get("/appointments", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def list_appointments(
    db: Session = Depends(get_db),
    mode: str = Query(default="list", pattern="^(list|day|week|biweekly|month)$"),
    day: date | None = None,
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    status: list[str] | None = Query(default=None),
    provider_id: int | None = Query(default=None),
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = Query(default="start_time", pattern="^(start_time|id)$"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    finalize_elapsed_appointments(db)
    stmt = _staff_appointments_select(
        mode=mode,
        day=day,
        month=month,
        year=year,
        status_list=status,
        provider_id=provider_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = (
        db.scalar(
            select(func.count()).select_from(stmt.with_only_columns(Appointment.id).order_by(None).subquery())
        )
        or 0
    )
    offset = (page - 1) * page_size
    appointments = db.execute(stmt.offset(offset).limit(page_size)).unique().scalars().all()
    data = [_appointment_to_crud_out(a) for a in appointments]
    return ok_response(
        {"items": data, "total": total, "page": page, "page_size": page_size},
        "Citas consultadas correctamente",
    )


@router.get("/appointments/export.xlsx", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def export_appointments_xlsx(
    db: Session = Depends(get_db),
    mode: str = Query(default="list", pattern="^(list|day|week|biweekly|month)$"),
    day: date | None = None,
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    status: list[str] | None = Query(default=None),
    provider_id: int | None = Query(default=None),
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = Query(default="start_time", pattern="^(start_time|id)$"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
):
    finalize_elapsed_appointments(db)
    stmt = _staff_appointments_select(
        mode=mode,
        day=day,
        month=month,
        year=year,
        status_list=status,
        provider_id=provider_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    appointments = db.execute(stmt).unique().scalars().all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Citas"
    ws.append(
        ["id", "proveedor_nit", "proveedor_nombre", "inicio_utc", "duracion_min", "estado", "descripcion_material"]
    )
    for a in appointments:
        pname = a.provider.company_name if a.provider else ""
        ws.append(
            [
                int(a.id),
                int(a.provider_id),
                pname,
                a.start_time.isoformat(),
                int(a.duration_minutes),
                a.status.value if hasattr(a.status, "value") else str(a.status),
                (a.material_description or "").replace("\n", " ")[:2000],
            ]
        )
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="citas_export.xlsx"'},
    )


@router.get("/appointments/{appointment_id}", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    finalize_elapsed_appointments(db)
    appointment = db.execute(
        select(Appointment).options(joinedload(Appointment.provider)).where(Appointment.id == appointment_id)
    ).unique().scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    return ok_response(_appointment_to_crud_out(appointment), "Cita consultada correctamente")


@router.post("/appointments", dependencies=[Depends(require_roles("Admin"))])
def create_appointment(
    payload: AppointmentIn,
    db: Session = Depends(get_db),
):
    if not db.get(Provider, payload.provider_id):
        raise HTTPException(status_code=400, detail="El proveedor no existe")
    assert_start_within_windows(db, payload.start_time)
    reserve_slot_fifo_or_raise(db, payload.start_time, payload.duration_minutes)
    appointment = Appointment(**payload.model_dump())
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    notify_staff_review_needed(db, appointment)
    db.commit()
    appointment = db.execute(
        select(Appointment).options(joinedload(Appointment.provider)).where(Appointment.id == appointment.id)
    ).unique().scalar_one()
    return ok_response(_appointment_to_crud_out(appointment), "Cita creada correctamente")


@router.put("/appointments/{appointment_id}", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    updates = payload.model_dump(exclude_unset=True)
    if "provider_id" in updates and not db.get(Provider, updates["provider_id"]):
        raise HTTPException(status_code=400, detail="El proveedor no existe")
    next_start = updates.get("start_time", appointment.start_time)
    next_duration = updates.get("duration_minutes", appointment.duration_minutes)
    if "start_time" in updates:
        assert_start_within_windows(db, next_start)
    if "start_time" in updates or "duration_minutes" in updates:
        reserve_slot_fifo_or_raise(
            db,
            start_time=next_start,
            duration_minutes=next_duration,
            exclude_appointment_id=appointment.id,
        )
    actor_id = principal.document_id
    critical_keys = {"status", "start_time", "duration_minutes", "material_description"}
    snapshots: dict[str, object] = {}
    for key in updates:
        if key in critical_keys:
            snapshots[key] = getattr(appointment, key)
    for key, value in updates.items():
        setattr(appointment, key, value)
    now = datetime.now(timezone.utc)
    changed_labels: list[str] = []
    field_labels = {
        "status": "estado",
        "start_time": "fecha y hora",
        "duration_minutes": "duración",
        "material_description": "descripción",
    }
    for key, old_val in snapshots.items():
        new_val = getattr(appointment, key)
        if old_val == new_val:
            continue
        changed_labels.append(field_labels.get(key, key))
        db.add(
            ChangeLog(
                actor_id=actor_id,
                appointment_id=appointment.id,
                action="update_field",
                description=f"Campo {key} actualizado",
                created_at=now,
                critical_field=key,
                old_value=str(old_val),
                new_value=str(new_val),
            )
        )
    if changed_labels:
        notify_provider_appointment_updated(
            db,
            appointment,
            summary=f"La empresa actualizó {', '.join(changed_labels)} de tu cita.",
        )
    db.commit()
    appointment = db.execute(
        select(Appointment).options(joinedload(Appointment.provider)).where(Appointment.id == appointment_id)
    ).unique().scalar_one()
    return ok_response(_appointment_to_crud_out(appointment), "Cita actualizada correctamente")


@router.delete("/appointments/{appointment_id}", dependencies=[Depends(require_roles("Admin"))])
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    db.delete(appointment)
    db.commit()
    return ok_response(None, "Cita eliminada correctamente")


@router.get("/appointment-franjas", dependencies=[Depends(require_roles("Admin", "Logistica", "Proveedor"))])
def list_appointment_franjas(db: Session = Depends(get_db)):
    wins = list_windows_ordered(db)
    data = [
        AppointmentWindowOut(
            id=w.id,
            start_local=w.start_local.strftime("%H:%M"),
            end_local=w.end_local.strftime("%H:%M"),
            sort_order=w.sort_order,
        ).model_dump()
        for w in wins
    ]
    return ok_response(
        {
            "franjas": data,
            "hint": format_schedule_hint(wins),
            "slot_minutes": 90,
            "timezone": settings.business_timezone,
        },
        "Franjas consultadas correctamente",
    )


@router.get("/appointment-franjas/resolved", dependencies=[Depends(require_roles("Admin", "Logistica", "Proveedor"))])
def get_resolved_appointment_franjas(day: date = Query(...), db: Session = Depends(get_db)):
    date_windows = list_date_windows_ordered(db, day)
    if date_windows:
        windows = date_windows
        source = "date_override"
    else:
        windows = list_windows_ordered(db)
        source = "weekly"
    data = [
        AppointmentWindowOut(
            id=w.id,
            start_local=w.start_local.strftime("%H:%M"),
            end_local=w.end_local.strftime("%H:%M"),
            sort_order=w.sort_order,
        ).model_dump()
        for w in windows
    ]
    return ok_response(
        {
            "day": str(day),
            "source": source,
            "franjas": data,
            "slot_minutes": 90,
            "timezone": settings.business_timezone,
        },
        "Franjas resueltas correctamente",
    )


@router.put("/appointment-franjas", dependencies=[Depends(require_roles("Admin"))])
def replace_appointment_franjas(payload: AppointmentWindowsReplace, db: Session = Depends(get_db)):
    parsed = _parse_and_validate_windows(payload.franjas, "Franjas semanales inválidas")
    _assert_weekly_windows_do_not_break_existing_appointments(db, parsed)
    wins = replace_windows(db, parsed)
    data = [
        AppointmentWindowOut(
            id=x.id,
            start_local=x.start_local.strftime("%H:%M"),
            end_local=x.end_local.strftime("%H:%M"),
            sort_order=x.sort_order,
        ).model_dump()
        for x in wins
    ]
    return ok_response(
        {
            "franjas": data,
            "hint": format_schedule_hint(wins),
            "slot_minutes": 90,
            "timezone": settings.business_timezone,
        },
        "Franjas actualizadas correctamente",
    )


@router.get("/appointment-franjas/fecha", dependencies=[Depends(require_roles("Admin"))])
def list_appointment_franjas_for_date(day: date = Query(...), db: Session = Depends(get_db)):
    tz = ZoneInfo(settings.business_timezone)
    local_today = datetime.now(tz).date()
    appointments_count = _appointments_count_on_local_day(db, day)
    can_edit = day >= local_today and appointments_count == 0
    wins = list_date_windows_ordered(db, day)
    data = [
        AppointmentWindowOut(
            id=x.id,
            start_local=x.start_local.strftime("%H:%M"),
            end_local=x.end_local.strftime("%H:%M"),
            sort_order=x.sort_order,
        ).model_dump()
        for x in wins
    ]
    return ok_response(
        {
            "day": str(day),
            "franjas": data,
            "appointments_count": appointments_count,
            "is_past": day < local_today,
            "can_edit": can_edit,
        },
        "Franjas por fecha consultadas correctamente",
    )


@router.get("/appointment-franjas/fecha/resumen", dependencies=[Depends(require_roles("Admin", "Logistica", "Proveedor"))])
def list_appointment_franjas_date_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    start_day = date(year, month, 1)
    if month == 12:
        end_day = date(year + 1, 1, 1)
    else:
        end_day = date(year, month + 1, 1)
    rows = (
        db.execute(
            select(AppointmentDateWindow.day)
            .where(AppointmentDateWindow.day >= start_day, AppointmentDateWindow.day < end_day)
            .group_by(AppointmentDateWindow.day)
            .order_by(AppointmentDateWindow.day.asc())
        )
        .scalars()
        .all()
    )
    return ok_response(
        {"override_days": [str(d) for d in rows]},
        "Resumen de franjas por fecha consultado correctamente",
    )


@router.put("/appointment-franjas/fecha", dependencies=[Depends(require_roles("Admin"))])
def replace_appointment_franjas_for_date(payload: AppointmentDateWindowReplace, db: Session = Depends(get_db)):
    day = datetime.strptime(payload.day, "%Y-%m-%d").date()
    tz = ZoneInfo(settings.business_timezone)
    local_today = datetime.now(tz).date()
    if day < local_today:
        raise HTTPException(status_code=400, detail="No se pueden editar franjas de días pasados.")
    if _appointments_count_on_local_day(db, day) > 0:
        raise HTTPException(status_code=409, detail="No se puede editar esta fecha porque ya tiene citas agendadas.")
    parsed = _parse_and_validate_windows(payload.franjas, "Franjas por fecha inválidas")
    wins = replace_date_windows(db, day, parsed)
    data = [
        AppointmentWindowOut(
            id=x.id,
            start_local=x.start_local.strftime("%H:%M"),
            end_local=x.end_local.strftime("%H:%M"),
            sort_order=x.sort_order,
        ).model_dump()
        for x in wins
    ]
    return ok_response({"day": str(day), "franjas": data}, "Franjas por fecha actualizadas correctamente")


@router.delete("/appointment-franjas/fecha", dependencies=[Depends(require_roles("Admin"))])
def delete_appointment_franjas_for_date(day: date = Query(...), db: Session = Depends(get_db)):
    tz = ZoneInfo(settings.business_timezone)
    local_today = datetime.now(tz).date()
    if day < local_today:
        raise HTTPException(status_code=400, detail="No se pueden modificar franjas de días pasados.")
    if _appointments_count_on_local_day(db, day) > 0:
        raise HTTPException(status_code=409, detail="No se puede quitar la excepción porque esa fecha ya tiene citas.")
    clear_date_windows(db, day)
    return ok_response({"day": str(day)}, "Franjas por fecha eliminadas correctamente")


@router.put("/appointment-franjas/fecha/lote", dependencies=[Depends(require_roles("Admin"))])
def replace_appointment_franjas_for_date_bulk(payload: AppointmentDateWindowBulkReplace, db: Session = Depends(get_db)):
    start_day = datetime.strptime(payload.start_day, "%Y-%m-%d").date()
    end_day = datetime.strptime(payload.end_day, "%Y-%m-%d").date()
    if end_day < start_day:
        raise HTTPException(status_code=400, detail="La fecha final debe ser mayor o igual a la fecha inicial.")
    selected_weekdays = sorted(set(int(x) for x in payload.iso_weekdays if 1 <= int(x) <= 7))
    if not selected_weekdays:
        raise HTTPException(status_code=400, detail="Debes seleccionar al menos un día ISO (1..7).")
    parsed = _parse_and_validate_windows(payload.franjas, "Franjas de lote inválidas")
    tz = ZoneInfo(settings.business_timezone)
    local_today = datetime.now(tz).date()
    if end_day < local_today:
        raise HTTPException(status_code=400, detail="El rango debe incluir hoy o fechas futuras.")
    if start_day < local_today:
        start_day = local_today
    applied_days: list[str] = []
    skipped_days: list[dict[str, str]] = []
    cursor = start_day
    while cursor <= end_day:
        if cursor.isoweekday() not in selected_weekdays:
            cursor += timedelta(days=1)
            continue
        if cursor < local_today:
            skipped_days.append({"day": str(cursor), "reason": "past_day"})
            cursor += timedelta(days=1)
            continue
        if _appointments_count_on_local_day(db, cursor) > 0:
            skipped_days.append({"day": str(cursor), "reason": "has_appointments"})
            cursor += timedelta(days=1)
            continue
        replace_date_windows(db, cursor, parsed)
        applied_days.append(str(cursor))
        cursor += timedelta(days=1)
    return ok_response(
        {"applied_days": applied_days, "skipped_days": skipped_days},
        "Franjas por lote aplicadas correctamente",
    )


@router.get("/analytics/summary", dependencies=[Depends(require_roles("Admin"))])
def analytics_summary(
    range_mode: str = Query(default="today", alias="range", pattern="^(today|week|biweekly|month)$"),
    db: Session = Depends(get_db),
):
    finalize_elapsed_appointments(db)
    tz = ZoneInfo(settings.business_timezone)
    local_now = datetime.now(tz)
    local_today_start = datetime(local_now.year, local_now.month, local_now.day, tzinfo=tz)
    local_today_end = local_today_start + timedelta(days=1)
    local_range_start, local_range_end = business_local_range_bounds(range_mode, local_now, tz)
    range_start_utc = local_range_start.astimezone(timezone.utc)
    range_end_utc = local_range_end.astimezone(timezone.utc)

    # Totales por estado para el rango seleccionado (filtro de analítica).
    rows_status = (
        db.execute(
            select(Appointment.status, func.count())
            .where(
                Appointment.start_time >= range_start_utc,
                Appointment.start_time < range_end_utc,
            )
            .group_by(Appointment.status)
        )
        .all()
    )
    totales: dict[str, int] = {}
    for st, cnt in rows_status:
        key = st.value if hasattr(st, "value") else str(st)
        totales[key] = int(cnt)

    # Totales por estado del día actual (sección de barras diarias).
    rows_status_today = (
        db.execute(
            select(Appointment.status, func.count())
            .where(
                Appointment.start_time >= local_today_start.astimezone(timezone.utc),
                Appointment.start_time < local_today_end.astimezone(timezone.utc),
            )
            .group_by(Appointment.status)
        )
        .all()
    )
    totales_hoy: dict[str, int] = {}
    for st, cnt in rows_status_today:
        key = st.value if hasattr(st, "value") else str(st)
        totales_hoy[key] = int(cnt)
    local_cutoff = local_today_start - timedelta(days=30)
    cutoff = local_cutoff.astimezone(timezone.utc)
    day_col = cast(Appointment.start_time, Date)
    day_rows = (
        db.execute(
            select(day_col.label("d"), func.count())
            .where(Appointment.start_time >= cutoff)
            .group_by(day_col)
            .order_by(day_col.asc())
        )
        .all()
    )
    citas_30 = [{"fecha": str(d), "cantidad": int(c)} for d, c in day_rows]
    week_start_local, week_end_local = business_local_range_bounds("week", local_now, tz)
    week_start = week_start_local.astimezone(timezone.utc)
    week_end = week_end_local.astimezone(timezone.utc)
    weekday_rows = (
        db.execute(
            select(day_col.label("d"), func.count())
            .where(Appointment.start_time >= week_start, Appointment.start_time < week_end)
            .group_by(day_col)
            .order_by(day_col.asc())
        )
        .all()
    )
    weekday_map = {str(d): int(c) for d, c in weekday_rows}
    day_names = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    citas_por_dia_semana = []
    for offset in range(7):
        d = (week_start_local + timedelta(days=offset)).date()
        iso = str(d)
        citas_por_dia_semana.append(
            {
                "fecha": iso,
                "dia": day_names[offset],
                "cantidad": weekday_map.get(iso, 0),
            }
        )
    # Top proveedores: siempre del mes actual (hora local del negocio), top 10.
    local_month_start = datetime(local_now.year, local_now.month, 1, tzinfo=tz)
    if local_now.month == 12:
        local_next_month_start = datetime(local_now.year + 1, 1, 1, tzinfo=tz)
    else:
        local_next_month_start = datetime(local_now.year, local_now.month + 1, 1, tzinfo=tz)
    month_start_utc = local_month_start.astimezone(timezone.utc)
    month_end_utc = local_next_month_start.astimezone(timezone.utc)

    top_rows = (
        db.execute(
            select(Appointment.provider_id, Provider.company_name, func.count())
            .join(Provider, Appointment.provider_id == Provider.nit)
            .where(Appointment.start_time >= month_start_utc, Appointment.start_time < month_end_utc)
            .group_by(Appointment.provider_id, Provider.company_name)
            .order_by(func.count().desc())
            .limit(10)
        )
        .all()
    )
    top_proveedores = [
        {"nit": int(nit), "nombre": nombre or "", "cantidad": int(cnt)} for nit, nombre, cnt in top_rows
    ]
    total = int(
        db.execute(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.start_time >= range_start_utc, Appointment.start_time < range_end_utc)
        ).scalar_one()
        or 0
    )
    out = AnalyticsSummaryOut(
        totales_por_estado=totales,
        totales_por_estado_hoy=totales_hoy,
        citas_ultimos_30_dias=citas_30,
        citas_por_dia_semana=citas_por_dia_semana,
        top_proveedores=top_proveedores,
        total_citas=total,
    )
    return ok_response(out.model_dump(), "Analítica generada correctamente")


@router.get("/reminders", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def list_reminders(
    db: Session = Depends(get_db),
    appointment_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
):
    stmt = select(ReminderExecution).order_by(ReminderExecution.executed_at.desc(), ReminderExecution.id.desc())
    if appointment_id is not None:
        stmt = stmt.where(ReminderExecution.appointment_id == appointment_id)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    offset = (page - 1) * page_size
    rows = db.execute(stmt.offset(offset).limit(page_size)).scalars().all()
    items = [
        {
            "id": r.id,
            "appointment_id": r.appointment_id,
            "kind": r.kind,
            "status": r.status,
            "detail": r.detail or "",
            "executed_at": r.executed_at,
        }
        for r in rows
    ]
    return ok_response({"items": items, "total": total, "page": page, "page_size": page_size}, "Recordatorios consultados")


@router.get("/change-logs", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def list_change_logs(
    db: Session = Depends(get_db),
    actor_id: str | None = Query(default=None, max_length=30),
    appointment_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    # Logística solo puede consultar su propio historial.
    effective_actor_id = actor_id.strip() if actor_id and actor_id.strip() else None
    if principal.role_name == "Logistica":
        effective_actor_id = principal.document_id

    stmt = select(ChangeLog).order_by(ChangeLog.created_at.desc())
    if effective_actor_id:
        stmt = stmt.where(ChangeLog.actor_id == effective_actor_id)
    if appointment_id is not None:
        stmt = stmt.where(ChangeLog.appointment_id == appointment_id)

    logs = db.execute(stmt).scalars().all()

    system_logs: list[AdminEvent] = []
    if appointment_id is None:
        system_stmt = select(AdminEvent).order_by(AdminEvent.created_at.desc())
        if effective_actor_id:
            system_stmt = system_stmt.where(AdminEvent.actor_id == effective_actor_id)
        system_logs = db.execute(system_stmt).scalars().all()

    data = [_change_log_to_out(db, log) for log in logs] + [_admin_event_to_out(db, event) for event in system_logs]
    data.sort(key=lambda x: (x["created_at"], x["id"]), reverse=True)
    total = len(data)
    offset = (page - 1) * page_size
    page_items = data[offset : offset + page_size]
    return ok_response(
        {"items": page_items, "total": total, "page": page, "page_size": page_size},
        "Historial consultado correctamente",
    )


@router.get("/change-logs/{log_id}", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def get_change_log(log_id: int, db: Session = Depends(get_db)):
    log = db.get(ChangeLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    return ok_response(_change_log_to_out(db, log), "Historial consultado correctamente")


@router.post("/change-logs", dependencies=[Depends(require_roles("Admin"))])
def create_change_log(payload: ChangeLogIn, db: Session = Depends(get_db)):
    if not db.get(User, payload.actor_id):
        raise HTTPException(status_code=400, detail="El actor no existe")
    if not db.get(Appointment, payload.appointment_id):
        raise HTTPException(status_code=400, detail="La cita no existe")
    log = ChangeLog(**payload.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return ok_response(_change_log_to_out(db, log), "Historial creado correctamente")


@router.put("/change-logs/{log_id}", dependencies=[Depends(require_roles("Admin"))])
def update_change_log(log_id: int, payload: ChangeLogUpdate, db: Session = Depends(get_db)):
    log = db.get(ChangeLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    updates = payload.model_dump(exclude_unset=True)
    if "actor_id" in updates and not db.get(User, updates["actor_id"]):
        raise HTTPException(status_code=400, detail="El actor no existe")
    if "appointment_id" in updates and not db.get(Appointment, updates["appointment_id"]):
        raise HTTPException(status_code=400, detail="La cita no existe")
    for key, value in updates.items():
        setattr(log, key, value)
    db.commit()
    db.refresh(log)
    return ok_response(_change_log_to_out(db, log), "Historial actualizado correctamente")


@router.delete("/change-logs/{log_id}", dependencies=[Depends(require_roles("Admin"))])
def delete_change_log(log_id: int, db: Session = Depends(get_db)):
    log = db.get(ChangeLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    db.delete(log)
    db.commit()
    return ok_response(None, "Historial eliminado correctamente")
