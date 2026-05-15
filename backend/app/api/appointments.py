from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import SecurityPrincipal, get_db, require_roles
from app.core.responses import ok_response
from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit_log import AuditLog
from app.models.provider import Provider
from app.models.user import UserRole
from app.core.config import settings
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentExtend,
    AppointmentOut,
    AppointmentProviderCancel,
    AppointmentProviderReschedule,
    AppointmentUpdateStatus,
)
from app.services.appointment_service import (
    can_extend_without_overlap,
    enforce_minimum_notice,
    finalize_elapsed_appointments,
    reserve_slot_fifo_or_raise,
    slot_conflict_check,
)
from app.services.appointment_windows import SLOT_MINUTES, assert_start_within_windows, list_date_windows_ordered
from app.services.notification_service import (
    notify_provider_appointment_updated,
    notify_staff_provider_cancelled,
    notify_staff_review_needed,
)
from app.services.range_bounds import business_local_range_bounds

router = APIRouter(prefix="/appointments", tags=["appointments"])


def _title_from_appointment(appointment: Appointment) -> str:
    text = appointment.material_description or ""
    first = text.split("\n", 1)[0].strip()
    return (first[:120] if first else "Cita")


def _serialize(appointment: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=appointment.id,
        provider_id=str(int(appointment.provider_id)),
        provider_name=appointment.provider.full_name,
        title=_title_from_appointment(appointment),
        material_description=appointment.material_description,
        start_time=appointment.start_time,
        duration_minutes=appointment.duration_minutes,
        status=appointment.status,
    )


def _local_day_utc_bounds(target_day: date) -> tuple[datetime, datetime]:
    tz = ZoneInfo(settings.business_timezone)
    local_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def _staff_modification_actions(db: Session, appointment_id: int) -> list[str]:
    return list(
        db.execute(
            select(AuditLog.action)
            .where(
                AuditLog.appointment_id == appointment_id,
                AuditLog.action.in_(["update_status", "extend_duration"]),
            )
            .order_by(AuditLog.id.asc())
        ).scalars()
    )


def _assert_not_already_modified_by_staff(db: Session, appointment_id: int) -> None:
    already_modified = db.execute(
        select(AuditLog.id)
        .where(
            AuditLog.appointment_id == appointment_id,
            AuditLog.action.in_(["update_status", "extend_duration"]),
        )
        .limit(1)
    ).scalar_one_or_none()
    if already_modified is not None:
        raise HTTPException(
            status_code=409,
            detail="Esta cita ya fue modificada por administración y no puede volver a modificarse.",
        )


def _assert_logistics_business_rules(
    *,
    db: Session,
    appt: Appointment,
    principal: SecurityPrincipal,
    target_action: str,
) -> None:
    if principal.role_name != UserRole.logistica:
        return
    if appt.status in {
        AppointmentStatus.cancelado,
        AppointmentStatus.finalizada,
        AppointmentStatus.no_presentada,
    }:
        raise HTTPException(
            status_code=409,
            detail="Esta cita ya está cerrada y no permite más cambios desde Logística.",
        )
    actions = _staff_modification_actions(db, appt.id)
    if len(actions) >= 2:
        raise HTTPException(
            status_code=409,
            detail="Esta cita ya tuvo los cambios permitidos en Logística.",
        )
    if len(actions) == 0:
        return
    first_action = actions[0]
    if appt.status == AppointmentStatus.revisado and first_action == "update_status":
        if target_action == "update_status":
            return
        raise HTTPException(
            status_code=409,
            detail="Cuando la cita está revisada, solo puedes hacer la confirmación de estado.",
        )
    raise HTTPException(
        status_code=409,
        detail="Esta cita ya fue modificada y no permite más cambios desde Logística.",
    )


@router.post("", response_model=AppointmentOut)
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_roles(UserRole.proveedor)),
):
    provider_id = int(principal.subject)
    day_local = payload.start_time.astimezone(ZoneInfo(settings.business_timezone)).date()
    start_utc, end_utc = _local_day_utc_bounds(day_local)
    already_same_day = db.execute(
        select(Appointment.id)
        .where(
            Appointment.provider_id == provider_id,
            Appointment.status != AppointmentStatus.cancelado,
            Appointment.start_time >= start_utc,
            Appointment.start_time < end_utc,
        )
        .limit(1)
    ).scalar_one_or_none()
    if already_same_day is not None:
        raise HTTPException(
            status_code=400,
            detail="Ya tienes una cita agendada para ese día. Solo se permite una cita por día.",
        )
    date_windows = list_date_windows_ordered(db, day_local)
    if not date_windows:
        raise HTTPException(
            status_code=400,
            detail="Este día no tiene franjas habilitadas para citas. Solo puedes agendar en fechas que la empresa abrió en el calendario de franjas.",
        )
    enforce_minimum_notice(payload.start_time, minimum_hours=settings.appointment_minimum_notice_hours)
    assert_start_within_windows(db, payload.start_time)
    reserve_slot_fifo_or_raise(db, payload.start_time, payload.duration_minutes)

    body = f"{payload.title.strip()}\n\n{payload.material_description.strip()}"
    appointment = Appointment(
        provider_id=provider_id,
        material_description=body,
        start_time=payload.start_time,
        duration_minutes=payload.duration_minutes,
        status=AppointmentStatus.sin_revision,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    notify_staff_review_needed(db, appointment)
    db.commit()
    return _serialize(appointment)


@router.get("")
def list_appointments(
    mode: str = Query(default="list", pattern="^(list|day|week|biweekly|month)$"),
    day: date | None = None,
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    status: list[str] | None = Query(default=None, description="Filtrar por uno o más estados de cita"),
    provider_id: int | None = Query(default=None, description="Filtrar por NIT proveedor (solo staff)"),
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = Query(default="start_time", pattern="^(start_time|id)$"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(
        require_roles(UserRole.admin, UserRole.logistica, UserRole.proveedor)
    ),
):
    finalize_elapsed_appointments(db)
    stmt = select(Appointment).options(joinedload(Appointment.provider))
    if principal.role_name == UserRole.proveedor:
        stmt = stmt.where(Appointment.provider_id == int(principal.subject))
    elif provider_id is not None:
        stmt = stmt.where(Appointment.provider_id == provider_id)

    if status:
        status_enums = []
        for s in status:
            try:
                status_enums.append(AppointmentStatus(s))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Estado inválido: {s}")
        stmt = stmt.where(Appointment.status.in_(status_enums))

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

    total = (
        db.scalar(
            select(func.count()).select_from(stmt.with_only_columns(Appointment.id).order_by(None).subquery())
        )
        or 0
    )

    offset = (page - 1) * page_size
    rows = db.execute(stmt.offset(offset).limit(page_size)).unique().scalars().all()
    return ok_response(
        {
            "items": [_serialize(a).model_dump() for a in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "Citas obtenidas",
    )


@router.get("/conflict-check")
def check_slot_conflict(
    start_time: datetime = Query(...),
    duration_minutes: int = Query(default=90, ge=15, le=480),
    exclude_appointment_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(
        require_roles(UserRole.admin, UserRole.logistica, UserRole.proveedor)
    ),
):
    """Indica si fecha/hora/duración colisionarían con otra cita."""
    conflict = slot_conflict_check(db, start_time, duration_minutes, exclude_appointment_id)
    return ok_response({"conflict": conflict}, "Verificación de conflicto")


@router.get("/available-slots")
def list_available_slots_for_provider_day(
    day: date = Query(...),
    exclude_appointment_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_roles(UserRole.proveedor)),
):
    tz = ZoneInfo(settings.business_timezone)
    minimum_hours = settings.appointment_minimum_notice_hours
    minimum_start_utc = datetime.now(timezone.utc) + timedelta(hours=minimum_hours)
    windows = list_date_windows_ordered(db, day)
    source = "date_override"
    if not windows:
        return ok_response(
            {
                "day": str(day),
                "slot_minutes": SLOT_MINUTES,
                "source": "none",
                "available_times": [],
                "minimum_notice_hours": minimum_hours,
                "unavailable_reason": "no_windows",
                "unavailable_message": "Este día no tiene franjas habilitadas para citas.",
            },
            "Disponibilidad obtenida",
        )
    start_utc, end_utc = _local_day_utc_bounds(day)
    provider_id = int(principal.subject)
    same_day_stmt = (
        select(Appointment.id)
        .where(
            Appointment.provider_id == provider_id,
            Appointment.status != AppointmentStatus.cancelado,
            Appointment.start_time >= start_utc,
            Appointment.start_time < end_utc,
        )
        .limit(1)
    )
    if exclude_appointment_id is not None:
        same_day_stmt = same_day_stmt.where(Appointment.id != exclude_appointment_id)
    if db.execute(same_day_stmt).scalar_one_or_none() is not None:
        return ok_response(
            {
                "day": str(day),
                "slot_minutes": SLOT_MINUTES,
                "source": source,
                "available_times": [],
                "minimum_notice_hours": minimum_hours,
                "unavailable_reason": "provider_has_appointment",
                "unavailable_message": "Ya tienes una cita agendada para este día. Solo se permite una cita por día.",
            },
            "Disponibilidad obtenida",
        )
    appointments = (
        db.execute(
            select(Appointment).where(
                Appointment.start_time >= start_utc,
                Appointment.start_time < end_utc,
                Appointment.status != AppointmentStatus.cancelado,
            )
        )
        .scalars()
        .all()
    )
    available_times: list[str] = []
    slots_in_window = 0
    slots_after_notice = 0
    for w in windows:
        start_minutes = w.start_local.hour * 60 + w.start_local.minute
        end_minutes = w.end_local.hour * 60 + w.end_local.minute
        t = start_minutes
        while t <= end_minutes:
            hh = t // 60
            mm = t % 60
            local_dt = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
            cand_start_utc = local_dt.astimezone(timezone.utc)
            cand_end_utc = cand_start_utc + timedelta(minutes=90)
            slots_in_window += 1
            if cand_start_utc < minimum_start_utc:
                t += SLOT_MINUTES
                continue
            slots_after_notice += 1
            overlap = False
            for appt in appointments:
                if exclude_appointment_id is not None and appt.id == exclude_appointment_id:
                    continue
                appt_end = appt.start_time + timedelta(minutes=appt.duration_minutes)
                if cand_start_utc < appt_end and cand_end_utc > appt.start_time:
                    overlap = True
                    break
            if not overlap:
                available_times.append(f"{hh:02d}:{mm:02d}")
            t += SLOT_MINUTES
    payload = {
        "day": str(day),
        "slot_minutes": SLOT_MINUTES,
        "source": source,
        "available_times": sorted(set(available_times)),
        "minimum_notice_hours": minimum_hours,
    }
    if not payload["available_times"]:
        earliest_local = minimum_start_utc.astimezone(tz)
        if slots_in_window == 0:
            payload["unavailable_reason"] = "no_valid_slots"
            payload["unavailable_message"] = "No hay horarios válidos en la franja habilitada para este día."
        elif slots_after_notice == 0:
            payload["unavailable_reason"] = "minimum_notice"
            payload["unavailable_message"] = (
                f"No puedes agendar para esta fecha porque la cita debe solicitarse con al menos "
                f"{minimum_hours} horas de anticipación. El primer horario que podrías elegir es después de las "
                f"{earliest_local.strftime('%H:%M')} ({settings.business_timezone})."
            )
            payload["earliest_bookable_at"] = earliest_local.isoformat()
        else:
            payload["unavailable_reason"] = "fully_booked"
            payload["unavailable_message"] = (
                "Disponibilidad llena: todos los horarios de esta franja ya fueron tomados por otras citas."
            )
    return ok_response(payload, "Disponibilidad obtenida")


@router.patch("/{appointment_id}/status", response_model=AppointmentOut)
def update_status(
    appointment_id: int,
    payload: AppointmentUpdateStatus,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_roles(UserRole.admin, UserRole.logistica)),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    _assert_logistics_business_rules(
        db=db,
        appt=appt,
        principal=principal,
        target_action="update_status",
    )
    if payload.status == AppointmentStatus.cancelado:
        if principal.role_name == UserRole.logistica:
            raise HTTPException(status_code=403, detail="Logística no está autorizada para cancelar citas")
        if principal.role_name != UserRole.admin:
            now_utc = datetime.now(timezone.utc)
            if appt.start_time - now_utc < timedelta(hours=24):
                raise HTTPException(
                    status_code=400,
                    detail="La cita solo se puede cancelar con minimo 24 horas de anticipacion",
                )
    old_status = appt.status
    appt.status = payload.status
    db.add(
        AuditLog(
            actor_id=principal.document_id,
            appointment_id=appt.id,
            action="update_status",
            description=f"Estado cambiado de {old_status.value} a {payload.status.value}",
            created_at=datetime.now(timezone.utc),
            critical_field="estado",
            old_value=old_status.value,
            new_value=payload.status.value,
        )
    )
    notify_provider_appointment_updated(
        db,
        appt,
        summary=f"La empresa cambió el estado de tu cita de {old_status.value} a {payload.status.value}.",
    )
    db.commit()
    db.refresh(appt)
    return _serialize(appt)


@router.patch("/{appointment_id}/extend", response_model=AppointmentOut)
def extend_appointment(
    appointment_id: int,
    payload: AppointmentExtend,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_roles(UserRole.admin, UserRole.logistica)),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    _assert_logistics_business_rules(
        db=db,
        appt=appt,
        principal=principal,
        target_action="extend_duration",
    )
    if not can_extend_without_overlap(db, appt, payload.extra_minutes):
        raise HTTPException(status_code=409, detail="No se puede extender: existe otra cita a continuación")
    old_duration = appt.duration_minutes
    appt.duration_minutes += payload.extra_minutes
    db.add(
        AuditLog(
            actor_id=principal.document_id,
            appointment_id=appt.id,
            action="extend_duration",
            description=f"Duración extendida de {old_duration} a {appt.duration_minutes} minutos (+{payload.extra_minutes})",
            created_at=datetime.now(timezone.utc),
            critical_field="duracion_minutos",
            old_value=str(old_duration),
            new_value=str(appt.duration_minutes),
        )
    )
    notify_provider_appointment_updated(
        db,
        appt,
        summary=f"La empresa extendió la duración de tu cita a {appt.duration_minutes} minutos.",
    )
    db.commit()
    db.refresh(appt)
    return _serialize(appt)


@router.patch("/{appointment_id}/reschedule", response_model=AppointmentOut)
def provider_reschedule_appointment(
    appointment_id: int,
    payload: AppointmentProviderReschedule,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_roles(UserRole.proveedor)),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    if int(appt.provider_id) != int(principal.subject):
        raise HTTPException(status_code=403, detail="No autorizado para reprogramar esta cita")
    if appt.status in {AppointmentStatus.cancelado, AppointmentStatus.finalizada, AppointmentStatus.no_presentada}:
        raise HTTPException(status_code=400, detail="Esta cita ya no puede reprogramarse")

    provider_id = int(principal.subject)
    day_local = payload.start_time.astimezone(ZoneInfo(settings.business_timezone)).date()
    start_utc, end_utc = _local_day_utc_bounds(day_local)
    already_same_day = db.execute(
        select(Appointment.id)
        .where(
            Appointment.provider_id == provider_id,
            Appointment.status != AppointmentStatus.cancelado,
            Appointment.start_time >= start_utc,
            Appointment.start_time < end_utc,
            Appointment.id != appointment_id,
        )
        .limit(1)
    ).scalar_one_or_none()
    if already_same_day is not None:
        raise HTTPException(
            status_code=400,
            detail="Ya tienes una cita agendada para ese día. Solo se permite una cita por día.",
        )
    date_windows = list_date_windows_ordered(db, day_local)
    if not date_windows:
        raise HTTPException(
            status_code=400,
            detail="Este día no tiene franjas habilitadas para citas. Solo puedes agendar en fechas que la empresa abrió en el calendario de franjas.",
        )
    enforce_minimum_notice(payload.start_time, minimum_hours=settings.appointment_minimum_notice_hours)
    assert_start_within_windows(db, payload.start_time)
    reserve_slot_fifo_or_raise(
        db,
        payload.start_time,
        appt.duration_minutes,
        exclude_appointment_id=appointment_id,
    )

    old_start = appt.start_time
    appt.start_time = payload.start_time
    if appt.status not in {
        AppointmentStatus.cancelado,
        AppointmentStatus.finalizada,
        AppointmentStatus.no_presentada,
    }:
        appt.status = AppointmentStatus.sin_revision
    db.add(
        AuditLog(
            actor_id=str(principal.subject),
            appointment_id=appt.id,
            action="provider_reschedule",
            description=(
                "Proveedor reprograma cita de "
                f"{old_start.astimezone(ZoneInfo(settings.business_timezone)).isoformat()} a "
                f"{payload.start_time.astimezone(ZoneInfo(settings.business_timezone)).isoformat()}"
            ),
            created_at=datetime.now(timezone.utc),
            critical_field="start_time",
            old_value=old_start.isoformat(),
            new_value=payload.start_time.isoformat(),
        )
    )
    notify_staff_review_needed(db, appt)
    db.commit()
    db.refresh(appt)
    return _serialize(appt)


@router.post("/{appointment_id}/provider-cancel", response_model=AppointmentOut)
def provider_cancel_appointment(
    appointment_id: int,
    payload: AppointmentProviderCancel,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_roles(UserRole.proveedor)),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    if int(appt.provider_id) != int(principal.subject):
        raise HTTPException(status_code=403, detail="No autorizado para cancelar esta cita")
    if appt.status in {AppointmentStatus.cancelado, AppointmentStatus.finalizada, AppointmentStatus.no_presentada}:
        raise HTTPException(status_code=400, detail="Esta cita ya no puede cancelarse")
    now_utc = datetime.now(timezone.utc)
    if appt.start_time - now_utc < timedelta(hours=2):
        raise HTTPException(status_code=400, detail="La cita solo se puede cancelar con mínimo 2 horas de anticipación")
    appt.status = AppointmentStatus.cancelado
    reason = payload.reason.strip()
    provider = db.get(Provider, int(appt.provider_id))
    provider_label = provider.company_name if provider else None
    db.add(
        AuditLog(
            actor_id=str(principal.subject),
            appointment_id=appt.id,
            action="provider_cancel",
            description=f"Proveedor cancela cita. Motivo: {reason}",
            created_at=datetime.now(timezone.utc),
        )
    )
    notify_staff_provider_cancelled(db, appt, reason=reason, provider_label=provider_label)
    db.commit()
    db.refresh(appt)
    return _serialize(appt)
