from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import Date, cast, delete, extract, func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import SecurityPrincipal, get_db, get_security_principal, require_roles
from app.core.config import settings
from app.core.responses import ok_response
from app.core.security import get_password_hash, verify_password
from app.models.appointment import Appointment, AppointmentStatus
from app.models.admin_event import AdminEvent
from app.models.audit_log import AuditLog, ChangeLog
from app.models.appointment_date_window import AppointmentDateWindow
from app.models.credential import Credential
from app.models.provider import Provider
from app.models.warehouse import Warehouse
from app.models.warehouse_unload_team import WarehouseUnloadTeam
from app.models.profile_photo import ProfilePhoto
from app.models.reminder_run import ReminderExecution
from app.models.role import Role
from app.models.user import User, UserRole
from app.services.credential_cleanup import delete_credential_fully, release_email_for_reuse
from app.services.email_dispatch import dispatch_welcome_provider, dispatch_welcome_staff
from app.services.provider_account import (
    build_provider_out_dict,
    delete_provider_immediate,
    format_provider_update_detail,
    notify_provider_and_admins,
    reactivate_provider,
    suspend_provider,
)
from app.services.notification_service import (
    notify_provider_appointment_updated,
    notify_staff_review_needed,
    notify_warehouse_schedule_updated,
)
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
    ProviderSuspendIn,
    ProviderUpdate,
    ProfileMeOut,
    ProfileMeUpdate,
    ProfilePasswordChange,
    RoleIn,
    RoleOut,
    UserCrudOut,
    UserIn,
    UserUpdate,
    WarehouseIn,
    WarehouseOut,
    WarehouseUnloadTeamsNamesIn,
    WarehouseUpdate,
)
from app.services.cloudinary_service import upload_profile_photo
from app.services.appointment_windows import (
    MIN_SLOT_MINUTES,
    MAX_SLOT_MINUTES,
    appointment_matches_slot,
    assert_appointment_slot,
    clear_date_windows,
    format_schedule_hint,
    get_active_warehouse_or_raise,
    get_team_scheduled_iso_weekdays,
    iter_bookable_slots,
    list_date_windows_ordered,
    list_team_open_days_in_month,
    list_team_override_days_in_month,
    list_team_provider_bookable_days_in_month,
    list_warehouse_open_days_in_month,
    replace_date_windows,
    resolve_team_windows_for_day,
    list_windows_ordered,
    replace_windows,
    slot_duration_minutes,
)
from app.services.appointment_service import finalize_elapsed_appointments, reserve_slot_fifo_or_raise
from app.services.range_bounds import (
    appointment_local_date_sql,
    build_daily_counts_in_range,
    business_local_range_bounds,
)
from app.services.warehouse_scope import (
    ROLE_ADMIN_BODEGA,
    assert_warehouse_access,
    enforce_query_warehouse_id,
    list_user_warehouse_ids,
    resolve_allowed_warehouse_ids,
    role_requires_warehouse_assignments,
    sync_user_warehouse_assignments,
    validate_warehouse_ids_exist,
)
router = APIRouter(prefix="/crud", tags=["crud"])

STAFF_APPOINTMENT_ROLES = ("Admin", "Logistica", "AdminBodega")
WAREHOUSE_OPS_ROLES = ("Admin", "AdminBodega")
STAFF_AUDIT_ROLES = ("Admin", "Logistica", "AdminBodega")


def _local_day_utc_bounds(target_day: date) -> tuple[datetime, datetime]:
    tz = ZoneInfo(settings.business_timezone)
    local_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def _appointments_count_on_local_day(
    db: Session,
    target_day: date,
    warehouse_id: int | None = None,
    warehouse_unload_team_id: int | None = None,
) -> int:
    start_utc, end_utc = _local_day_utc_bounds(target_day)
    stmt = (
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
    )
    if warehouse_id is not None:
        stmt = stmt.where(Appointment.warehouse_id == warehouse_id)
    if warehouse_unload_team_id is not None:
        stmt = stmt.where(Appointment.warehouse_unload_team_id == warehouse_unload_team_id)
    return int(db.execute(stmt).scalar_one() or 0)


def _schedule_actor_label(principal: SecurityPrincipal) -> str:
    return f"{principal.role_name} ({principal.document_id})"


def _principal_actor_email(db: Session, principal: SecurityPrincipal) -> str | None:
    if principal.user is None or not principal.user.credential_id:
        return None
    cred = db.get(Credential, principal.user.credential_id)
    return str(cred.email).strip() if cred and cred.email else None


def _warehouse_team_labels(db: Session, warehouse_id: int, team_id: int) -> tuple[str, str]:
    warehouse = db.get(Warehouse, warehouse_id)
    team = db.get(WarehouseUnloadTeam, team_id)
    wh_name = warehouse.name if warehouse else f"Bodega #{warehouse_id}"
    team_name = team.name if team else f"Equipo #{team_id}"
    return wh_name, team_name


def _franjas_ranges_text(franjas: list) -> str:
    parts: list[str] = []
    for row in franjas:
        if isinstance(row, dict):
            start = str(row.get("start_local", ""))
            end = str(row.get("end_local", ""))
        else:
            start = getattr(row, "start_local", "")
            end = getattr(row, "end_local", "")
            if hasattr(start, "strftime"):
                start = start.strftime("%H:%M")
            if hasattr(end, "strftime"):
                end = end.strftime("%H:%M")
        if start and end:
            parts.append(f"{start}–{end}")
    return ", ".join(parts) if parts else "(sin franjas)"


def _window_to_out(window) -> dict:
    return AppointmentWindowOut(
        id=window.id,
        start_local=window.start_local.strftime("%H:%M"),
        end_local=window.end_local.strftime("%H:%M"),
        duration_minutes=slot_duration_minutes(window.start_local, window.end_local),
        sort_order=window.sort_order,
    ).model_dump()


def _warehouse_to_out(warehouse: Warehouse) -> dict:
    return WarehouseOut(
        id=warehouse.id,
        name=warehouse.name,
        address=warehouse.address,
        active=warehouse.active,
        sort_order=warehouse.sort_order,
        unload_teams=warehouse.unload_teams,
    ).model_dump()


def _assert_non_overlapping_windows(parsed: list[tuple], error_prefix: str = "Franja inválida") -> None:
    prev_end = None
    for idx, (hi, hf) in enumerate(parsed, start=1):
        if hf <= hi:
            raise HTTPException(status_code=400, detail="En cada franja la hora fin debe ser mayor que la de inicio")
        if prev_end is not None and hi < prev_end:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{error_prefix}: la franja #{idx} se solapa con la anterior "
                    f"(puede iniciar a las {prev_end.strftime('%H:%M')} o después; "
                    f"recibido inicio {hi.strftime('%H:%M')})."
                ),
            )
        prev_end = hf


def _parse_and_validate_windows(items: list, error_prefix: str) -> list[tuple]:
    parsed: list[tuple] = []
    for w in items:
        hi = datetime.strptime(w.start_local, "%H:%M").time()
        hf = datetime.strptime(w.end_local, "%H:%M").time()
        minutes = slot_duration_minutes(hi, hf)
        if minutes < MIN_SLOT_MINUTES or minutes > MAX_SLOT_MINUTES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{error_prefix}: cada turno debe durar entre {MIN_SLOT_MINUTES} "
                    f"y {MAX_SLOT_MINUTES} minutos."
                ),
            )
        parsed.append((hi, hf))
    parsed.sort(key=lambda x: (x[0].hour, x[0].minute))
    _assert_non_overlapping_windows(parsed, error_prefix)
    return parsed


def _time_allowed_in_windows(local_time, duration_minutes: int, windows: list[tuple]) -> bool:
    for start_local, end_local in windows:
        if appointment_matches_slot(local_time, duration_minutes, start_local, end_local):
            return True
    return False


def _resolve_franja_unload_team_id(
    db: Session, warehouse_id: int, unload_team_id: int | None, *, required: bool = False
) -> int | None:
    from app.services.unload_teams import list_active_unload_teams, resolve_unload_team_id_for_warehouse

    teams = list_active_unload_teams(db, warehouse_id)
    if not teams:
        if required:
            raise HTTPException(
                status_code=400,
                detail="La bodega no tiene equipos de descarga. Configúralos en Bodegas.",
            )
        return None
    if required and unload_team_id is None and len(teams) > 1:
        raise HTTPException(
            status_code=400,
            detail="Selecciona el equipo de descarga de la bodega para configurar sus horarios.",
        )
    strict = required and unload_team_id is not None
    return resolve_unload_team_id_for_warehouse(db, warehouse_id, unload_team_id, strict=strict)


def _assert_weekly_windows_do_not_break_existing_appointments(
    db: Session,
    weekly_windows: list[tuple],
    warehouse_id: int,
    warehouse_unload_team_id: int | None = None,
) -> None:
    tz = ZoneInfo(settings.business_timezone)
    local_today = datetime.now(tz).date()
    start_utc, _ = _local_day_utc_bounds(local_today)
    appt_stmt = select(Appointment.start_time, Appointment.duration_minutes).where(
        Appointment.status != AppointmentStatus.cancelado,
        Appointment.start_time >= start_utc,
        Appointment.warehouse_id == warehouse_id,
    )
    if warehouse_unload_team_id is not None:
        appt_stmt = appt_stmt.where(Appointment.warehouse_unload_team_id == warehouse_unload_team_id)
    appointments = db.execute(appt_stmt.order_by(Appointment.start_time.asc())).scalars().all()
    if not appointments:
        return

    override_days = set(
        db.execute(
            select(AppointmentDateWindow.day)
            .where(
                AppointmentDateWindow.day >= local_today,
                AppointmentDateWindow.warehouse_id == warehouse_id,
            )
            .group_by(AppointmentDateWindow.day)
        )
        .scalars()
        .all()
    )

    conflicts: list[str] = []
    for row in appointments:
        start_time, duration_minutes = row[0], row[1]
        aware_start = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        local_dt = aware_start.astimezone(tz)
        if local_dt.date() in override_days:
            continue
        if not _time_allowed_in_windows(local_dt.time(), int(duration_minutes), weekly_windows):
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


def _appointment_to_crud_out(
    appt: Appointment,
    *,
    logistics_extend_used: bool = False,
    logistics_extend_minutes: int = 0,
    total_extend_minutes: int = 0,
    original_duration_minutes: int | None = None,
) -> dict:
    pname = appt.provider.company_name if appt.provider else ""
    wname = appt.warehouse.name if appt.warehouse else ""
    team = getattr(appt, "warehouse_unload_team", None)
    team_name = team.name if team else ""
    return AppointmentCrudOut(
        id=appt.id,
        provider_id=int(appt.provider_id),
        provider_name=pname,
        warehouse_id=appt.warehouse_id,
        warehouse_name=wname,
        warehouse_unload_team_id=appt.warehouse_unload_team_id,
        warehouse_unload_team_name=team_name,
        material_description=appt.material_description,
        start_time=appt.start_time,
        duration_minutes=appt.duration_minutes,
        status=appt.status,
        logistics_extend_used=logistics_extend_used,
        logistics_extend_minutes=logistics_extend_minutes,
        total_extend_minutes=total_extend_minutes,
        original_duration_minutes=original_duration_minutes,
    ).model_dump()


def _extension_fields_for_appt(appt: Appointment, summaries: dict) -> dict:
    from app.services.appointment_extension import ExtensionSummary

    summary: ExtensionSummary | None = summaries.get(int(appt.id))
    if summary is None:
        return {
            "logistics_extend_used": False,
            "logistics_extend_minutes": 0,
            "total_extend_minutes": 0,
            "original_duration_minutes": int(appt.duration_minutes),
        }
    return {
        "logistics_extend_used": summary.logistics_extend_used,
        "logistics_extend_minutes": summary.logistics_extend_minutes,
        "total_extend_minutes": summary.total_extend_minutes,
        "original_duration_minutes": summary.original_duration_minutes,
    }


def _user_to_out(user: User, db: Session) -> UserCrudOut:
    email = user.credential.email if user.credential else ""
    role_name = user.role.name if user.role else ""
    warehouse_ids = (
        list_user_warehouse_ids(db, user.document_id)
        if role_requires_warehouse_assignments(role_name)
        else []
    )
    return UserCrudOut(
        document_id=user.document_id,
        email=email,
        full_name=user.full_name,
        role_id=user.role_id,
        role_name=role_name,
        warehouse_ids=warehouse_ids,
    )


def _resolve_appointment_warehouse_scope(
    db: Session,
    principal: SecurityPrincipal,
    warehouse_id: int | None,
) -> tuple[int | None, list[int] | None]:
    allowed = resolve_allowed_warehouse_ids(db, principal)
    if allowed is None:
        if warehouse_id is not None:
            get_active_warehouse_or_raise(db, warehouse_id)
        return warehouse_id, None
    wh_filter = enforce_query_warehouse_id(allowed, warehouse_id)
    if wh_filter is not None:
        get_active_warehouse_or_raise(db, wh_filter)
        return wh_filter, None
    return None, allowed


def _warehouse_ids_for_role(role_name: str, warehouse_ids: list[int] | None) -> list[int]:
    """Solo Logística y AdminBodega conservan bodegas; otros roles las ignoran."""
    ids = [int(w) for w in (warehouse_ids or []) if int(w) > 0]
    if role_requires_warehouse_assignments(role_name):
        return ids
    return []


def _validate_user_role_and_warehouses(db: Session, role_name: str, warehouse_ids: list[int]) -> None:
    if role_requires_warehouse_assignments(role_name):
        validate_warehouse_ids_exist(db, warehouse_ids)


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


def _change_log_to_out(db: Session, log: ChangeLog, appointment: Appointment | None = None) -> dict:
    name, role = _actor_display(db, log.actor_id)
    appt = appointment
    if appt is None and log.appointment_id is not None:
        appt = db.get(Appointment, log.appointment_id)
    warehouse_name = ""
    warehouse_id = None
    if appt is not None:
        warehouse_id = int(appt.warehouse_id)
        if appt.warehouse is not None:
            warehouse_name = appt.warehouse.name or ""
        elif warehouse_id:
            wh = db.get(Warehouse, warehouse_id)
            warehouse_name = wh.name if wh else ""
    return ChangeLogOut(
        id=log.id,
        actor_id=log.actor_id,
        appointment_id=log.appointment_id,
        action=log.action,
        description=log.description,
        created_at=log.created_at,
        actor_name=name,
        actor_role=role,
        warehouse_id=warehouse_id,
        warehouse_name=warehouse_name,
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
    data = [_user_to_out(user, db).model_dump() for user in users]
    return ok_response(data, "Usuarios consultados correctamente")


@router.get("/users/{document_id}", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def get_user(document_id: str, db: Session = Depends(get_db)):
    user = db.get(User, document_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return ok_response(_user_to_out(user, db).model_dump(), "Usuario consultado correctamente")


@router.post("/users", dependencies=[Depends(require_roles("Admin"))])
def create_user(
    payload: UserIn,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    role = db.get(Role, payload.role_id)
    if not role:
        raise HTTPException(status_code=400, detail="El rol no existe")
    if role.name not in ("Admin", "Logistica", ROLE_ADMIN_BODEGA):
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden crear usuarios internos con rol Admin, Logistica o AdminBodega",
        )
    warehouse_ids = _warehouse_ids_for_role(role.name, payload.warehouse_ids)
    _validate_user_role_and_warehouses(db, role.name, warehouse_ids)
    if db.get(User, payload.document_id):
        raise HTTPException(status_code=400, detail="El documento ya está registrado")
    email = str(payload.email).strip().lower()
    release_email_for_reuse(db, email)

    cred = Credential(email=email, password_hash=get_password_hash(payload.password))
    db.add(cred)
    db.flush()

    user = User(
        document_id=payload.document_id,
        full_name=payload.full_name,
        credential_id=cred.id,
        role_id=payload.role_id,
    )
    db.add(user)
    db.flush()
    if role_requires_warehouse_assignments(role.name):
        sync_user_warehouse_assignments(db, user.document_id, warehouse_ids)
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="user_create",
        description=f"Creó usuario interno {payload.full_name} ({payload.document_id})",
        target_document_id=payload.document_id,
    )
    db.commit()
    db.refresh(user)
    dispatch_welcome_staff(email, payload.full_name, role.name)
    return ok_response(_user_to_out(user, db).model_dump(), "Usuario creado correctamente")


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
    warehouse_ids_update = updates.pop("warehouse_ids", None)
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
    db.flush()
    role_name = user.role.name if user.role else ""
    if warehouse_ids_update is not None:
        wh_ids = _warehouse_ids_for_role(role_name, warehouse_ids_update)
        _validate_user_role_and_warehouses(db, role_name, wh_ids)
        sync_user_warehouse_assignments(
            db,
            user.document_id,
            wh_ids if role_requires_warehouse_assignments(role_name) else [],
        )
    elif not role_requires_warehouse_assignments(role_name):
        sync_user_warehouse_assignments(db, user.document_id, [])
    elif not list_user_warehouse_ids(db, user.document_id):
        raise HTTPException(
            status_code=400,
            detail="Este usuario debe tener al menos una bodega asignada.",
        )
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="user_update",
        description=f"Actualizó usuario interno {user.full_name} ({user.document_id})",
        target_document_id=user.document_id,
    )
    db.commit()
    db.refresh(user)
    return ok_response(_user_to_out(user, db).model_dump(), "Usuario actualizado correctamente")


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
    db.flush()
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="user_delete",
        description=f"Eliminó usuario interno {deleted_name} ({document_id})",
        target_document_id=document_id,
    )
    delete_credential_fully(db, cid)
    db.commit()
    return ok_response(None, "Usuario eliminado correctamente")


@router.post("/admin/release-email", dependencies=[Depends(require_roles("Admin"))])
def admin_release_email(
    email: str = Query(..., min_length=3, max_length=255),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    """Libera un correo eliminando credenciales huérfanas (sin usuario ni proveedor activo)."""
    removed = release_email_for_reuse(db, email)
    db.commit()
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="email_release",
        description=f"Liberó correo {email.strip().lower()} (credenciales: {removed or 'ninguna'})",
        target_document_id=None,
    )
    db.commit()
    return ok_response(
        {"email": email.strip().lower(), "removed_credential_ids": removed},
        "Correo liberado correctamente" if removed else "No había credenciales huérfanas para ese correo",
    )


@router.get("/profile/me", dependencies=[Depends(require_roles("Admin", "Logistica", "AdminBodega", "Proveedor"))])
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
    unload_teams = None
    if principal.provider is not None:
        unload_teams = int(principal.provider.unload_teams or 1)
    data = ProfileMeOut(
        document_id=document_id,
        role_name=role_name,
        full_name=full_name,
        email=cred.email,
        photo_url=photo.photo_url if photo else None,
        unload_teams=unload_teams,
    ).model_dump()
    return ok_response(data, "Perfil consultado correctamente")


@router.put("/profile/me", dependencies=[Depends(require_roles("Admin", "Logistica", "AdminBodega", "Proveedor"))])
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
        if payload.unload_teams is not None:
            principal.provider.unload_teams = payload.unload_teams
    db.commit()
    return get_my_profile(principal=principal, db=db)


@router.post("/profile/me/change-password", dependencies=[Depends(require_roles("Admin", "Logistica", "AdminBodega", "Proveedor"))])
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


@router.post("/profile/me/photo", dependencies=[Depends(require_roles("Admin", "Logistica", "AdminBodega", "Proveedor"))])
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


@router.delete("/profile/me/photo", dependencies=[Depends(require_roles("Admin", "Logistica", "AdminBodega", "Proveedor"))])
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
    data = [build_provider_out_dict(db, provider) for provider in providers]
    return ok_response(
        {"items": data, "total": len(data)},
        "Proveedores consultados correctamente",
    )


@router.get("/providers/{nit}", dependencies=[Depends(require_roles("Admin", "Logistica"))])
def get_provider(nit: int, db: Session = Depends(get_db)):
    provider = db.get(Provider, nit)
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return ok_response(build_provider_out_dict(db, provider), "Proveedor consultado correctamente")


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
    dispatch_welcome_provider(str(payload.company_email), payload.company_name)
    return ok_response(build_provider_out_dict(db, provider), "Proveedor creado correctamente")


@router.put("/providers/{nit}", dependencies=[Depends(require_roles("Admin"))])
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

    before = {
        "company_name": provider.company_name,
        "company_email": provider.company_email,
        "contact_name": provider.contact_name,
        "contact_document": provider.contact_document,
        "verification_digit": provider.verification_digit,
        "unload_teams": provider.unload_teams,
        "password_changed": False,
    }

    updates = payload.model_dump(exclude_unset=True)
    if "password" in updates:
        cred.password_hash = get_password_hash(updates.pop("password"))
        before["password_changed"] = True
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

    after = {
        "company_name": provider.company_name,
        "company_email": provider.company_email,
        "contact_name": provider.contact_name,
        "contact_document": provider.contact_document,
        "verification_digit": provider.verification_digit,
        "unload_teams": provider.unload_teams,
        "password_changed": before["password_changed"],
    }
    change_detail = format_provider_update_detail(before, after)

    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="provider_update",
        description=f"Actualizó proveedor {provider.company_name} (NIT {nit}): {change_detail}",
        target_document_id=str(nit),
    )
    db.commit()
    db.refresh(provider)
    notify_provider_and_admins(
        db,
        provider=provider,
        action="updated",
        detail=change_detail,
        actor_label=f"Admin {principal.document_id}",
    )
    return ok_response(build_provider_out_dict(db, provider), "Proveedor actualizado correctamente")


@router.post("/providers/{nit}/suspend", dependencies=[Depends(require_roles("Admin"))])
def suspend_provider_account(
    nit: int,
    payload: ProviderSuspendIn,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    provider = db.get(Provider, nit)
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    actor_email = _principal_actor_email(db, principal)
    suspend_provider(
        db,
        provider,
        reason=payload.reason,
        actor_id=principal.document_id,
        actor_email=actor_email,
    )
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="provider_suspend",
        description=f"Suspendió proveedor {provider.company_name} (NIT {nit}): {payload.reason.strip()}",
        target_document_id=str(nit),
    )
    db.commit()
    db.refresh(provider)
    return ok_response(build_provider_out_dict(db, provider), "Proveedor suspendido correctamente")


@router.post("/providers/{nit}/reactivate", dependencies=[Depends(require_roles("Admin"))])
def reactivate_provider_account(
    nit: int,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    provider = db.get(Provider, nit)
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    reactivate_provider(db, provider, actor_id=principal.document_id)
    _log_admin_event(
        db=db,
        actor_id=principal.document_id,
        action="provider_reactivate",
        description=f"Reactivó proveedor {provider.company_name} (NIT {nit})",
        target_document_id=str(nit),
    )
    db.commit()
    db.refresh(provider)
    return ok_response(build_provider_out_dict(db, provider), "Proveedor reactivado correctamente")


@router.delete("/providers/{nit}", dependencies=[Depends(require_roles("Admin"))])
def delete_provider(
    nit: int,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    provider = db.get(Provider, nit)
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    delete_provider_immediate(db, provider, actor_id=principal.document_id)
    db.commit()
    return ok_response(None, "Proveedor eliminado correctamente")


def _staff_appointments_select(
    *,
    mode: str,
    day: date | None,
    month: int | None,
    year: int | None,
    period: int | None = None,
    status_list: list[str] | None,
    provider_id: int | None,
    warehouse_id: int | None,
    allowed_warehouse_ids: list[int] | None = None,
    date_from: date | None,
    date_to: date | None,
    sort_by: str,
    sort_dir: str,
):
    stmt = select(Appointment).options(
        joinedload(Appointment.provider),
        joinedload(Appointment.warehouse),
        joinedload(Appointment.warehouse_unload_team),
    )
    if provider_id is not None:
        stmt = stmt.where(Appointment.provider_id == provider_id)
    if warehouse_id is not None:
        stmt = stmt.where(Appointment.warehouse_id == warehouse_id)
    elif allowed_warehouse_ids is not None:
        stmt = stmt.where(Appointment.warehouse_id.in_(allowed_warehouse_ids))

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
        start, end = _local_day_utc_bounds(day)
        stmt = stmt.where(Appointment.start_time >= start, Appointment.start_time < end)
    elif mode in ("week", "biweekly"):
        tz = ZoneInfo(settings.business_timezone)
        local_now = datetime.now(tz)
        period_arg = period if mode in ("week", "biweekly") else None
        start_local, end_local = business_local_range_bounds(
            mode, local_now, tz, period=period_arg
        )
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


@router.get("/appointments", dependencies=[Depends(require_roles(*STAFF_APPOINTMENT_ROLES))])
def list_appointments(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
    mode: str = Query(default="list", pattern="^(list|day|week|biweekly|month)$"),
    day: date | None = None,
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    period: int | None = Query(default=None, ge=1, le=6),
    status: list[str] | None = Query(default=None),
    provider_id: int | None = Query(default=None),
    warehouse_id: int | None = Query(default=None, ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = Query(default="start_time", pattern="^(start_time|id)$"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    finalize_elapsed_appointments(db)
    wh_filter, scope_ids = _resolve_appointment_warehouse_scope(db, principal, warehouse_id)
    stmt = _staff_appointments_select(
        mode=mode,
        day=day,
        month=month,
        year=year,
        period=period,
        status_list=status,
        provider_id=provider_id,
        warehouse_id=wh_filter,
        allowed_warehouse_ids=scope_ids,
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
    from app.services.appointment_extension import get_extension_summaries

    appt_ids = [a.id for a in appointments]
    ext_summaries = get_extension_summaries(
        db,
        appt_ids,
        current_durations={a.id: int(a.duration_minutes) for a in appointments},
    )
    data = [
        _appointment_to_crud_out(a, **_extension_fields_for_appt(a, ext_summaries)) for a in appointments
    ]
    return ok_response(
        {"items": data, "total": total, "page": page, "page_size": page_size},
        "Citas consultadas correctamente",
    )


@router.get("/appointments/export.xlsx", dependencies=[Depends(require_roles(*STAFF_APPOINTMENT_ROLES))])
def export_appointments_xlsx(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
    mode: str = Query(default="list", pattern="^(list|day|week|biweekly|month)$"),
    day: date | None = None,
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    period: int | None = Query(default=None, ge=1, le=6),
    status: list[str] | None = Query(default=None),
    provider_id: int | None = Query(default=None),
    warehouse_id: int | None = Query(default=None, ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = Query(default="start_time", pattern="^(start_time|id)$"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
):
    finalize_elapsed_appointments(db)
    wh_filter, scope_ids = _resolve_appointment_warehouse_scope(db, principal, warehouse_id)
    stmt = _staff_appointments_select(
        mode=mode,
        day=day,
        month=month,
        year=year,
        period=period,
        status_list=status,
        provider_id=provider_id,
        warehouse_id=wh_filter,
        allowed_warehouse_ids=scope_ids,
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
        [
            "id",
            "proveedor_nit",
            "proveedor_nombre",
            "bodega",
            "inicio_utc",
            "duracion_min",
            "estado",
            "descripcion_material",
        ]
    )
    for a in appointments:
        pname = a.provider.company_name if a.provider else ""
        wname = a.warehouse.name if a.warehouse else ""
        ws.append(
            [
                int(a.id),
                int(a.provider_id),
                pname,
                wname,
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


@router.get("/appointments/{appointment_id}", dependencies=[Depends(require_roles(*STAFF_APPOINTMENT_ROLES))])
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    finalize_elapsed_appointments(db)
    appointment = db.execute(
        select(Appointment)
        .options(
            joinedload(Appointment.provider),
            joinedload(Appointment.warehouse),
            joinedload(Appointment.warehouse_unload_team),
        )
        .where(Appointment.id == appointment_id)
    ).unique().scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    assert_warehouse_access(db, principal, appointment.warehouse_id)
    from app.services.appointment_extension import get_extension_summaries

    ext_summaries = get_extension_summaries(
        db,
        [appointment.id],
        current_durations={appointment.id: int(appointment.duration_minutes)},
    )
    return ok_response(
        _appointment_to_crud_out(appointment, **_extension_fields_for_appt(appointment, ext_summaries)),
        "Cita consultada correctamente",
    )


@router.post("/appointments", dependencies=[Depends(require_roles(*WAREHOUSE_OPS_ROLES))])
def create_appointment(
    payload: AppointmentIn,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    if not db.get(Provider, payload.provider_id):
        raise HTTPException(status_code=400, detail="El proveedor no existe")
    get_active_warehouse_or_raise(db, payload.warehouse_id)
    assert_warehouse_access(db, principal, payload.warehouse_id)
    from app.services.unload_teams import get_unload_team_or_raise, list_active_unload_teams

    teams = list_active_unload_teams(db, payload.warehouse_id)
    team_id = payload.warehouse_unload_team_id or (teams[0].id if teams else None)
    if team_id is None:
        raise HTTPException(status_code=400, detail="La bodega no tiene equipos de descarga configurados.")
    team = get_unload_team_or_raise(db, payload.warehouse_id, team_id)
    assert_appointment_slot(
        db, payload.start_time, payload.duration_minutes, payload.warehouse_id, team.id
    )
    reserve_slot_fifo_or_raise(
        db,
        payload.start_time,
        payload.duration_minutes,
        team.id,
        provider_id=int(payload.provider_id),
    )
    data = payload.model_dump()
    data["warehouse_unload_team_id"] = team.id
    appointment = Appointment(**data)
    db.add(appointment)
    db.flush()
    notify_staff_review_needed(db, appointment)
    db.commit()
    appointment = db.execute(
        select(Appointment)
        .options(
            joinedload(Appointment.provider),
            joinedload(Appointment.warehouse),
            joinedload(Appointment.warehouse_unload_team),
        )
        .where(Appointment.id == appointment.id)
    ).unique().scalar_one()
    return ok_response(_appointment_to_crud_out(appointment), "Cita creada correctamente")


@router.put("/appointments/{appointment_id}", dependencies=[Depends(require_roles(*STAFF_APPOINTMENT_ROLES))])
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    assert_warehouse_access(db, principal, appointment.warehouse_id)
    updates = payload.model_dump(exclude_unset=True)
    from app.models.user import UserRole
    from app.services.appointment_windows import assert_appointment_fits_windows

    confirm_override = bool(updates.pop("confirm_non_standard_slot", False))
    staff_reason = str(updates.pop("staff_change_reason", "") or "").strip()
    if confirm_override:
        if principal.role_name not in STAFF_APPOINTMENT_ROLES:
            raise HTTPException(status_code=403, detail="No tiene permiso para confirmar este cambio")
        if len(staff_reason) < 10:
            raise HTTPException(
                status_code=400,
                detail="Debe indicar el motivo del cambio (mínimo 10 caracteres).",
            )

    if principal.role_name == UserRole.admin_bodega and "warehouse_id" in updates:
        if int(updates["warehouse_id"]) != int(appointment.warehouse_id):
            raise HTTPException(status_code=403, detail="No tiene permiso para cambiar la bodega de la cita")
    if principal.role_name == UserRole.logistica:
        if "warehouse_id" in updates and int(updates["warehouse_id"]) != int(appointment.warehouse_id):
            raise HTTPException(status_code=403, detail="Logística no puede cambiar la bodega de la cita")
        if "warehouse_unload_team_id" in updates and int(updates["warehouse_unload_team_id"]) != int(
            appointment.warehouse_unload_team_id
        ):
            raise HTTPException(status_code=403, detail="Logística no puede cambiar el equipo de descarga de la cita")
    if "provider_id" in updates and not db.get(Provider, updates["provider_id"]):
        raise HTTPException(status_code=400, detail="El proveedor no existe")
    if "warehouse_id" in updates:
        get_active_warehouse_or_raise(db, updates["warehouse_id"])
        assert_warehouse_access(db, principal, updates["warehouse_id"])
    next_start = updates.get("start_time", appointment.start_time)
    next_duration = updates.get("duration_minutes", appointment.duration_minutes)
    next_warehouse = updates.get("warehouse_id", appointment.warehouse_id)
    next_team = updates.get("warehouse_unload_team_id", appointment.warehouse_unload_team_id)
    if "warehouse_unload_team_id" in updates or "warehouse_id" in updates:
        from app.services.unload_teams import get_unload_team_or_raise

        get_unload_team_or_raise(db, next_warehouse, int(next_team))
    slot_fields = {"start_time", "duration_minutes", "warehouse_id", "warehouse_unload_team_id"}
    if updates.keys() & slot_fields:
        if confirm_override:
            assert_appointment_fits_windows(db, next_start, next_duration, next_warehouse, next_team)
        else:
            assert_appointment_slot(db, next_start, next_duration, next_warehouse, next_team)
        reserve_slot_fifo_or_raise(
            db,
            start_time=next_start,
            duration_minutes=next_duration,
            warehouse_unload_team_id=next_team,
            exclude_appointment_id=appointment.id,
            provider_id=int(appointment.provider_id),
        )
    actor_id = principal.document_id
    critical_keys = {
        "status",
        "start_time",
        "duration_minutes",
        "material_description",
        "warehouse_id",
        "warehouse_unload_team_id",
    }
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
        "warehouse_id": "bodega",
        "warehouse_unload_team_id": "equipo de descarga",
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
    if confirm_override and (updates.keys() & slot_fields):
        db.add(
            ChangeLog(
                actor_id=actor_id,
                appointment_id=appointment.id,
                action="staff_override_reschedule",
                description=staff_reason,
                created_at=now,
                critical_field="reprogramacion_confirmada",
                old_value=None,
                new_value=staff_reason,
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
        select(Appointment)
        .options(
            joinedload(Appointment.provider),
            joinedload(Appointment.warehouse),
            joinedload(Appointment.warehouse_unload_team),
        )
        .where(Appointment.id == appointment_id)
    ).unique().scalar_one()
    from app.services.appointment_extension import get_extension_summaries

    ext_summaries = get_extension_summaries(
        db,
        [appointment.id],
        current_durations={appointment.id: int(appointment.duration_minutes)},
    )
    return ok_response(
        _appointment_to_crud_out(appointment, **_extension_fields_for_appt(appointment, ext_summaries)),
        "Cita actualizada correctamente",
    )


@router.get("/warehouses", dependencies=[Depends(require_roles("Admin", "Logistica", "AdminBodega", "Proveedor"))])
def list_warehouses(
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    stmt = select(Warehouse).order_by(Warehouse.sort_order, Warehouse.id)
    if active_only:
        stmt = stmt.where(Warehouse.active.is_(True))
    allowed = resolve_allowed_warehouse_ids(db, principal)
    if allowed is not None:
        if not allowed:
            return ok_response([], "Bodegas consultadas correctamente")
        stmt = stmt.where(Warehouse.id.in_(allowed))
    rows = db.execute(stmt).scalars().all()
    return ok_response(
        [_warehouse_to_out(w) for w in rows],
        "Bodegas consultadas correctamente",
    )


@router.post("/warehouses", dependencies=[Depends(require_roles("Admin"))])
def create_warehouse(payload: WarehouseIn, db: Session = Depends(get_db)):
    existing = db.execute(select(Warehouse.id).where(Warehouse.name == payload.name.strip())).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Ya existe una bodega con ese nombre.")
    warehouse = Warehouse(
        name=payload.name.strip(),
        address=(payload.address or "").strip() or None,
        active=payload.active,
        sort_order=payload.sort_order,
        unload_teams=payload.unload_teams,
    )
    db.add(warehouse)
    db.flush()
    from app.services.unload_teams import sync_warehouse_unload_teams

    sync_warehouse_unload_teams(db, warehouse.id, payload.unload_teams)
    db.commit()
    db.refresh(warehouse)
    return ok_response(_warehouse_to_out(warehouse), "Bodega creada correctamente")


@router.put("/warehouses/{warehouse_id}", dependencies=[Depends(require_roles(*WAREHOUSE_OPS_ROLES))])
def update_warehouse(
    warehouse_id: int,
    payload: WarehouseUpdate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    assert_warehouse_access(db, principal, warehouse_id)
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Bodega no encontrada")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"]:
        updates["name"] = updates["name"].strip()
        dup = db.execute(
            select(Warehouse.id).where(Warehouse.name == updates["name"], Warehouse.id != warehouse_id)
        ).scalar_one_or_none()
        if dup is not None:
            raise HTTPException(status_code=409, detail="Ya existe otra bodega con ese nombre.")
    if "address" in updates:
        updates["address"] = (updates["address"] or "").strip() or None
    for key, value in updates.items():
        setattr(warehouse, key, value)
    if "unload_teams" in updates:
        from app.services.unload_teams import sync_warehouse_unload_teams

        sync_warehouse_unload_teams(db, warehouse.id, updates["unload_teams"])
    db.commit()
    db.refresh(warehouse)
    return ok_response(_warehouse_to_out(warehouse), "Bodega actualizada correctamente")


@router.put(
    "/warehouses/{warehouse_id}/unload-teams",
    dependencies=[Depends(require_roles(*WAREHOUSE_OPS_ROLES))],
)
def update_warehouse_unload_team_names(
    warehouse_id: int,
    payload: WarehouseUnloadTeamsNamesIn,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    from app.services.unload_teams import (
        unload_team_to_dict,
        update_warehouse_unload_team_names as apply_team_names,
    )

    assert_warehouse_access(db, principal, warehouse_id)
    if not db.get(Warehouse, warehouse_id):
        raise HTTPException(status_code=404, detail="Bodega no encontrada")
    name_by_id = {item.id: item.name for item in payload.teams}
    teams = apply_team_names(db, warehouse_id, name_by_id)
    db.commit()
    return ok_response(
        [unload_team_to_dict(t) for t in teams],
        "Nombres de equipos actualizados correctamente",
    )


@router.delete("/warehouses/{warehouse_id}", dependencies=[Depends(require_roles("Admin"))])
def deactivate_warehouse(warehouse_id: int, db: Session = Depends(get_db)):
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Bodega no encontrada")
    active_count = db.scalar(select(func.count()).select_from(Warehouse).where(Warehouse.active.is_(True))) or 0
    if warehouse.active and active_count <= 1:
        raise HTTPException(status_code=400, detail="Debe permanecer al menos una bodega activa.")
    warehouse.active = False
    db.commit()
    return ok_response(_warehouse_to_out(warehouse), "Bodega desactivada correctamente")


@router.delete("/appointments/{appointment_id}", dependencies=[Depends(require_roles(*WAREHOUSE_OPS_ROLES))])
def delete_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    assert_warehouse_access(db, principal, appointment.warehouse_id)
    db.delete(appointment)
    db.commit()
    return ok_response(None, "Cita eliminada correctamente")


@router.get("/appointment-franjas", dependencies=[Depends(require_roles("Admin", "Logistica", "AdminBodega", "Proveedor"))])
def list_appointment_franjas(
    warehouse_id: int = Query(..., ge=1),
    unload_team_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    get_active_warehouse_or_raise(db, warehouse_id)
    assert_warehouse_access(db, principal, warehouse_id)
    team_id = _resolve_franja_unload_team_id(db, warehouse_id, unload_team_id)
    wins = list_windows_ordered(db, warehouse_id, team_id)
    data = [_window_to_out(w) for w in wins]
    return ok_response(
        {
            "warehouse_id": warehouse_id,
            "unload_team_id": team_id,
            "franjas": data,
            "hint": format_schedule_hint(wins),
            "timezone": settings.business_timezone,
        },
        "Franjas consultadas correctamente",
    )


@router.get("/appointment-franjas/resolved", dependencies=[Depends(require_roles("Admin", "Logistica", "AdminBodega", "Proveedor"))])
def get_resolved_appointment_franjas(
    day: date = Query(...),
    warehouse_id: int = Query(..., ge=1),
    unload_team_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    get_active_warehouse_or_raise(db, warehouse_id)
    assert_warehouse_access(db, principal, warehouse_id)
    team_id = _resolve_franja_unload_team_id(db, warehouse_id, unload_team_id)
    windows, source = resolve_team_windows_for_day(db, day, warehouse_id, team_id)
    data = [_window_to_out(w) for w in windows]
    return ok_response(
        {
            "day": str(day),
            "warehouse_id": warehouse_id,
            "unload_team_id": team_id,
            "source": source,
            "franjas": data,
            "timezone": settings.business_timezone,
        },
        "Franjas resueltas correctamente",
    )


@router.put("/appointment-franjas", dependencies=[Depends(require_roles(*WAREHOUSE_OPS_ROLES))])
def replace_appointment_franjas(
    payload: AppointmentWindowsReplace,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    get_active_warehouse_or_raise(db, payload.warehouse_id)
    assert_warehouse_access(db, principal, payload.warehouse_id)
    team_id = _resolve_franja_unload_team_id(db, payload.warehouse_id, payload.unload_team_id, required=True)
    parsed = _parse_and_validate_windows(payload.franjas, "Franjas semanales inválidas")
    _assert_weekly_windows_do_not_break_existing_appointments(
        db, parsed, payload.warehouse_id, team_id
    )
    wins = replace_windows(db, payload.warehouse_id, parsed, team_id)
    data = [_window_to_out(x) for x in wins]
    wh_name, team_name = _warehouse_team_labels(db, payload.warehouse_id, team_id)
    notify_warehouse_schedule_updated(
        db,
        warehouse_id=payload.warehouse_id,
        summary=(
            f"Franjas semanales actualizadas en {wh_name}, muelle «{team_name}». "
            f"Turnos: {_franjas_ranges_text(data)} ({settings.business_timezone})."
        ),
        actor_label=_schedule_actor_label(principal),
    )
    return ok_response(
        {
            "warehouse_id": payload.warehouse_id,
            "unload_team_id": team_id,
            "franjas": data,
            "hint": format_schedule_hint(wins),
            "timezone": settings.business_timezone,
        },
        "Franjas actualizadas correctamente",
    )


@router.get("/appointment-franjas/fecha", dependencies=[Depends(require_roles(*WAREHOUSE_OPS_ROLES))])
def list_appointment_franjas_for_date(
    day: date = Query(...),
    warehouse_id: int = Query(..., ge=1),
    unload_team_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    get_active_warehouse_or_raise(db, warehouse_id)
    assert_warehouse_access(db, principal, warehouse_id)
    team_id = _resolve_franja_unload_team_id(db, warehouse_id, unload_team_id)
    tz = ZoneInfo(settings.business_timezone)
    local_today = datetime.now(tz).date()
    appointments_count = _appointments_count_on_local_day(db, day, warehouse_id, team_id)
    can_edit = day >= local_today and appointments_count == 0
    wins = list_date_windows_ordered(db, day, warehouse_id, team_id)
    data = [_window_to_out(x) for x in wins]
    return ok_response(
        {
            "day": str(day),
            "warehouse_id": warehouse_id,
            "unload_team_id": team_id,
            "franjas": data,
            "appointments_count": appointments_count,
            "is_past": day < local_today,
            "can_edit": can_edit,
        },
        "Franjas por fecha consultadas correctamente",
    )


@router.get("/appointment-franjas/fecha/resumen", dependencies=[Depends(require_roles("Admin", "Logistica", "AdminBodega", "Proveedor"))])
def list_appointment_franjas_date_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    warehouse_id: int = Query(..., ge=1),
    unload_team_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    get_active_warehouse_or_raise(db, warehouse_id)
    assert_warehouse_access(db, principal, warehouse_id)
    start_day = date(year, month, 1)
    if month == 12:
        end_day = date(year + 1, 1, 1)
    else:
        end_day = date(year, month + 1, 1)

    if unload_team_id is None:
        open_days = list_warehouse_open_days_in_month(db, year, month, warehouse_id)
        return ok_response(
            {
                "warehouse_id": warehouse_id,
                "unload_team_id": None,
                "open_days": open_days,
                "override_days": open_days,
                "has_weekly_franjas": None,
            },
            "Resumen de franjas por fecha consultado correctamente",
        )

    team_id = _resolve_franja_unload_team_id(db, warehouse_id, unload_team_id)
    override_days = list_team_override_days_in_month(db, year, month, warehouse_id, team_id)
    has_weekly = bool(list_windows_ordered(db, warehouse_id, team_id))
    if principal.role_name == UserRole.proveedor:
        open_days = list_team_provider_bookable_days_in_month(
            db, year, month, warehouse_id, team_id
        )
    else:
        open_days = list_team_open_days_in_month(db, year, month, warehouse_id, team_id)
    scheduled_iso_weekdays = sorted(get_team_scheduled_iso_weekdays(db, warehouse_id, team_id))
    return ok_response(
        {
            "warehouse_id": warehouse_id,
            "unload_team_id": team_id,
            "open_days": open_days,
            "override_days": override_days,
            "has_weekly_franjas": has_weekly,
            "scheduled_iso_weekdays": scheduled_iso_weekdays,
        },
        "Resumen de franjas por fecha consultado correctamente",
    )


@router.put("/appointment-franjas/fecha", dependencies=[Depends(require_roles(*WAREHOUSE_OPS_ROLES))])
def replace_appointment_franjas_for_date(
    payload: AppointmentDateWindowReplace,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    day = datetime.strptime(payload.day, "%Y-%m-%d").date()
    get_active_warehouse_or_raise(db, payload.warehouse_id)
    assert_warehouse_access(db, principal, payload.warehouse_id)
    team_id = _resolve_franja_unload_team_id(db, payload.warehouse_id, payload.unload_team_id, required=True)
    tz = ZoneInfo(settings.business_timezone)
    local_today = datetime.now(tz).date()
    if day < local_today:
        raise HTTPException(status_code=400, detail="No se pueden editar franjas de días pasados.")
    if _appointments_count_on_local_day(db, day, payload.warehouse_id, team_id) > 0:
        raise HTTPException(
            status_code=409,
            detail="No se puede editar esta fecha porque este muelle ya tiene citas programadas.",
        )
    parsed = _parse_and_validate_windows(payload.franjas, "Franjas por fecha inválidas")
    wins = replace_date_windows(db, day, payload.warehouse_id, parsed, team_id)
    data = [_window_to_out(x) for x in wins]
    wh_name, team_name = _warehouse_team_labels(db, payload.warehouse_id, team_id)
    notify_warehouse_schedule_updated(
        db,
        warehouse_id=payload.warehouse_id,
        summary=(
            f"Franjas del día {day.isoformat()} en {wh_name}, muelle «{team_name}». "
            f"Turnos: {_franjas_ranges_text(data)} ({settings.business_timezone})."
        ),
        actor_label=_schedule_actor_label(principal),
    )
    return ok_response(
        {"day": str(day), "warehouse_id": payload.warehouse_id, "franjas": data},
        "Franjas por fecha actualizadas correctamente",
    )


@router.delete("/appointment-franjas/fecha", dependencies=[Depends(require_roles(*WAREHOUSE_OPS_ROLES))])
def delete_appointment_franjas_for_date(
    day: date = Query(...),
    warehouse_id: int = Query(..., ge=1),
    unload_team_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    get_active_warehouse_or_raise(db, warehouse_id)
    assert_warehouse_access(db, principal, warehouse_id)
    team_id = _resolve_franja_unload_team_id(db, warehouse_id, unload_team_id, required=True)
    tz = ZoneInfo(settings.business_timezone)
    local_today = datetime.now(tz).date()
    if day < local_today:
        raise HTTPException(status_code=400, detail="No se pueden modificar franjas de días pasados.")
    if _appointments_count_on_local_day(db, day, warehouse_id, team_id) > 0:
        raise HTTPException(
            status_code=409,
            detail="No se puede quitar la excepción porque este muelle ya tiene citas ese día.",
        )
    clear_date_windows(db, day, warehouse_id, team_id)
    wh_name, team_name = _warehouse_team_labels(db, warehouse_id, team_id)
    notify_warehouse_schedule_updated(
        db,
        warehouse_id=warehouse_id,
        summary=(
            f"Se quitaron las franjas especiales del {day.isoformat()} en {wh_name}, "
            f"muelle «{team_name}» (vuelve el horario semanal)."
        ),
        actor_label=_schedule_actor_label(principal),
    )
    return ok_response(
        {"day": str(day), "warehouse_id": warehouse_id, "unload_team_id": team_id},
        "Franjas por fecha eliminadas correctamente",
    )


@router.put("/appointment-franjas/fecha/lote", dependencies=[Depends(require_roles(*WAREHOUSE_OPS_ROLES))])
def replace_appointment_franjas_for_date_bulk(
    payload: AppointmentDateWindowBulkReplace,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    get_active_warehouse_or_raise(db, payload.warehouse_id)
    assert_warehouse_access(db, principal, payload.warehouse_id)
    team_id = _resolve_franja_unload_team_id(db, payload.warehouse_id, payload.unload_team_id, required=True)
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
        if _appointments_count_on_local_day(db, cursor, payload.warehouse_id, team_id) > 0:
            skipped_days.append({"day": str(cursor), "reason": "has_appointments"})
            cursor += timedelta(days=1)
            continue
        replace_date_windows(db, cursor, payload.warehouse_id, parsed, team_id)
        applied_days.append(str(cursor))
        cursor += timedelta(days=1)
    if applied_days:
        wh_name, team_name = _warehouse_team_labels(db, payload.warehouse_id, team_id)
        notify_warehouse_schedule_updated(
            db,
            warehouse_id=payload.warehouse_id,
            summary=(
                f"Franjas por lote en {wh_name}, muelle «{team_name}», "
                f"{len(applied_days)} día(s) ({applied_days[0]} … {applied_days[-1]}). "
                f"Turnos: {_franjas_ranges_text(payload.franjas)} ({settings.business_timezone})."
            ),
            actor_label=_schedule_actor_label(principal),
        )
    return ok_response(
        {"applied_days": applied_days, "skipped_days": skipped_days},
        "Franjas por lote aplicadas correctamente",
    )


def _appointment_scope(warehouse_id: int | None):
    def apply(stmt):
        if warehouse_id is not None:
            return stmt.where(Appointment.warehouse_id == warehouse_id)
        return stmt

    return apply


@router.get("/analytics/summary", dependencies=[Depends(require_roles("Admin"))])
def analytics_summary(
    range_mode: str = Query(default="today", alias="range", pattern="^(today|week|biweekly|month)$"),
    period: int | None = Query(default=None, ge=1, le=6),
    day: date | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    warehouse_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    finalize_elapsed_appointments(db)
    if warehouse_id is not None:
        get_active_warehouse_or_raise(db, warehouse_id)
    scope = _appointment_scope(warehouse_id)
    tz = ZoneInfo(settings.business_timezone)
    tz_name = settings.business_timezone
    local_now = datetime.now(tz)
    if range_mode == "month" and month is not None and year is not None:
        local_now = datetime(int(year), int(month), 15, tzinfo=tz)
    period_arg = period if range_mode in ("week", "biweekly") else None
    if range_mode == "today":
        target_day = day if day is not None else local_now.date()
        range_start_utc, range_end_utc = _local_day_utc_bounds(target_day)
        local_range_start = datetime(target_day.year, target_day.month, target_day.day, tzinfo=tz)
        local_range_end = local_range_start + timedelta(days=1)
        local_today_start = local_range_start
        local_today_end = local_range_end
        local_now = datetime(
            target_day.year, target_day.month, target_day.day, 12, tzinfo=tz
        )
    else:
        local_today_start = datetime(local_now.year, local_now.month, local_now.day, tzinfo=tz)
        local_today_end = local_today_start + timedelta(days=1)
        local_range_start, local_range_end = business_local_range_bounds(
            range_mode, local_now, tz, period=period_arg
        )
        range_start_utc = local_range_start.astimezone(timezone.utc)
        range_end_utc = local_range_end.astimezone(timezone.utc)
    day_col = appointment_local_date_sql(Appointment.start_time, tz_name)

    # Totales por estado para el rango seleccionado (filtro de analítica).
    rows_status = (
        db.execute(
            scope(
                select(Appointment.status, func.count()).where(
                    Appointment.start_time >= range_start_utc,
                    Appointment.start_time < range_end_utc,
                )
            ).group_by(Appointment.status)
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
            scope(
                select(Appointment.status, func.count()).where(
                    Appointment.start_time >= local_today_start.astimezone(timezone.utc),
                    Appointment.start_time < local_today_end.astimezone(timezone.utc),
                )
            ).group_by(Appointment.status)
        )
        .all()
    )
    totales_hoy: dict[str, int] = {}
    for st, cnt in rows_status_today:
        key = st.value if hasattr(st, "value") else str(st)
        totales_hoy[key] = int(cnt)
    if range_mode == "today":
        totales_hoy = dict(totales)
    local_cutoff = local_today_start - timedelta(days=30)
    cutoff = local_cutoff.astimezone(timezone.utc)
    day_rows = (
        db.execute(
            scope(select(day_col.label("d"), func.count()).where(Appointment.start_time >= cutoff))
            .group_by(day_col)
            .order_by(day_col.asc())
        )
        .all()
    )
    citas_30 = [{"fecha": str(d), "cantidad": int(c)} for d, c in day_rows]
    chart_start_local = local_range_start
    chart_end_local = local_range_end
    if range_mode == "today":
        chart_start_local = local_range_start
        chart_end_local = local_range_end
    elif range_mode not in ("week", "biweekly"):
        chart_start_local, chart_end_local = business_local_range_bounds("week", local_now, tz)
    chart_start = chart_start_local.astimezone(timezone.utc)
    chart_end = chart_end_local.astimezone(timezone.utc)
    weekday_rows = (
        db.execute(
            scope(
                select(day_col.label("d"), func.count()).where(
                    Appointment.start_time >= chart_start,
                    Appointment.start_time < chart_end,
                )
            )
            .group_by(day_col)
            .order_by(day_col.asc())
        )
        .all()
    )
    weekday_map = {str(d): int(c) for d, c in weekday_rows}
    citas_por_dia_semana = build_daily_counts_in_range(
        chart_start_local, chart_end_local, weekday_map
    )
    # Top proveedores: si el rango es mensual, usa ese mes; si no, usa el mes actual.
    if range_mode == "month":
        month_start_utc = local_range_start.astimezone(timezone.utc)
        month_end_utc = local_range_end.astimezone(timezone.utc)
    else:
        local_month_start = datetime(local_now.year, local_now.month, 1, tzinfo=tz)
        if local_now.month == 12:
            local_next_month_start = datetime(local_now.year + 1, 1, 1, tzinfo=tz)
        else:
            local_next_month_start = datetime(local_now.year, local_now.month + 1, 1, tzinfo=tz)
        month_start_utc = local_month_start.astimezone(timezone.utc)
        month_end_utc = local_next_month_start.astimezone(timezone.utc)

    top_rows = (
        db.execute(
            scope(
                select(Appointment.provider_id, Provider.company_name, func.count())
                .join(Provider, Appointment.provider_id == Provider.nit)
                .where(
                    Appointment.start_time >= month_start_utc,
                    Appointment.start_time < month_end_utc,
                )
            )
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
            scope(
                select(func.count())
                .select_from(Appointment)
                .where(
                    Appointment.start_time >= range_start_utc,
                    Appointment.start_time < range_end_utc,
                )
            )
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


@router.get("/reminders", dependencies=[Depends(require_roles(*STAFF_APPOINTMENT_ROLES))])
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


@router.get("/change-logs", dependencies=[Depends(require_roles(*STAFF_AUDIT_ROLES))])
def list_change_logs(
    db: Session = Depends(get_db),
    actor_id: str | None = Query(default=None, max_length=30),
    appointment_id: int | None = Query(default=None),
    warehouse_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    allowed_warehouses = resolve_allowed_warehouse_ids(db, principal)
    if allowed_warehouses is not None and not allowed_warehouses:
        return ok_response(
            {"items": [], "total": 0, "page": page, "page_size": page_size},
            "Historial consultado correctamente",
        )

    if appointment_id is not None:
        appt = db.get(Appointment, appointment_id)
        if not appt:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        assert_warehouse_access(db, principal, appt.warehouse_id)

    if warehouse_id is not None:
        assert_warehouse_access(db, principal, warehouse_id)

    # Logística solo puede consultar su propio historial.
    effective_actor_id = actor_id.strip() if actor_id and actor_id.strip() else None
    if principal.role_name == UserRole.logistica:
        effective_actor_id = principal.document_id

    stmt = select(ChangeLog).order_by(ChangeLog.created_at.desc())
    scope_by_warehouse = allowed_warehouses is not None or warehouse_id is not None
    if scope_by_warehouse:
        stmt = stmt.join(Appointment, ChangeLog.appointment_id == Appointment.id)
    if effective_actor_id:
        stmt = stmt.where(ChangeLog.actor_id == effective_actor_id)
    if appointment_id is not None:
        stmt = stmt.where(ChangeLog.appointment_id == appointment_id)
    if warehouse_id is not None:
        stmt = stmt.where(Appointment.warehouse_id == int(warehouse_id))
    elif allowed_warehouses is not None:
        stmt = stmt.where(Appointment.warehouse_id.in_(allowed_warehouses))

    logs = db.execute(stmt).scalars().all()
    appointment_ids = {int(log.appointment_id) for log in logs if log.appointment_id is not None}
    appointments_by_id: dict[int, Appointment] = {}
    if appointment_ids:
        rows = db.execute(
            select(Appointment)
            .options(joinedload(Appointment.warehouse))
            .where(Appointment.id.in_(appointment_ids))
        ).unique().scalars().all()
        appointments_by_id = {int(a.id): a for a in rows}

    system_logs: list[AdminEvent] = []
    if appointment_id is None and principal.role_name == UserRole.admin:
        system_stmt = select(AdminEvent).order_by(AdminEvent.created_at.desc())
        if effective_actor_id:
            system_stmt = system_stmt.where(AdminEvent.actor_id == effective_actor_id)
        system_logs = db.execute(system_stmt).scalars().all()

    data = [
        _change_log_to_out(db, log, appointments_by_id.get(int(log.appointment_id)))
        for log in logs
        if log.appointment_id is not None
    ] + [_admin_event_to_out(db, event) for event in system_logs]
    data.sort(key=lambda x: (x["created_at"], x["id"]), reverse=True)
    total = len(data)
    offset = (page - 1) * page_size
    page_items = data[offset : offset + page_size]
    return ok_response(
        {"items": page_items, "total": total, "page": page, "page_size": page_size},
        "Historial consultado correctamente",
    )


@router.get("/change-logs/{log_id}", dependencies=[Depends(require_roles(*STAFF_AUDIT_ROLES))])
def get_change_log(
    log_id: int,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_security_principal),
):
    log = db.get(ChangeLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    appt = db.get(Appointment, log.appointment_id)
    if appt:
        assert_warehouse_access(db, principal, appt.warehouse_id)
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
