"""Pruebas de integracion: conflictos de horario y bodegas (SQLAlchemy + PostgreSQL)."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.appointment import Appointment, AppointmentStatus
from app.models.provider import Provider
from app.models.warehouse import Warehouse
from app.models.warehouse_unload_team import WarehouseUnloadTeam
from app.services.appointment_service import reserve_slot_fifo_or_raise
from app.services.appointment_windows import get_active_warehouse_or_raise
from app.services.unload_teams import list_active_unload_teams


def _unique_start(days_ahead: int = 30) -> datetime:
    base = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    return base.replace(minute=0, second=0, microsecond=0) + timedelta(
        minutes=random.randint(0, 11) * 5
    )


def _provider_id(db_session) -> int:
    pid = db_session.execute(select(Provider.nit).limit(1)).scalar_one_or_none()
    if pid is None:
        pytest.skip("No hay proveedores en BD; use seed o cree uno con test_db_crud_functions")
    return int(pid)


def _active_warehouse_id(db_session) -> int:
    wid = db_session.execute(
        select(Warehouse.id).where(Warehouse.active.is_(True)).order_by(Warehouse.id).limit(1)
    ).scalar_one_or_none()
    if wid is None:
        pytest.skip("No hay bodega activa; ejecute db/init/014_bodegas_franjas_flexibles.sql")
    return int(wid)


def _team_id(db_session, warehouse_id: int) -> int:
    teams = list_active_unload_teams(db_session, warehouse_id)
    if not teams:
        pytest.skip("Sin equipos de descarga; ejecute db/init/017_equipos_descarga_entidades.sql")
    return int(teams[0].id)


def _insert_appointment(
    db_session,
    *,
    provider_id: int,
    warehouse_id: int,
    start_time: datetime,
    duration_minutes: int = 60,
    warehouse_unload_team_id: int | None = None,
) -> Appointment:
    team_id = warehouse_unload_team_id or _team_id(db_session, warehouse_id)
    appt = Appointment(
        provider_id=provider_id,
        warehouse_id=warehouse_id,
        warehouse_unload_team_id=team_id,
        provider_team_index=1,
        material_description=f"pytest {uuid.uuid4().hex[:8]}",
        start_time=start_time,
        duration_minutes=duration_minutes,
        status=AppointmentStatus.sin_revision,
    )
    db_session.add(appt)
    db_session.flush()
    return appt


def test_get_active_warehouse_invalid_raises(db_session):
    with pytest.raises(HTTPException) as exc:
        get_active_warehouse_or_raise(db_session, 9_999_999)
    assert exc.value.status_code == 400
    assert "bodega" in exc.value.detail.lower()


def test_reserve_slot_overlap_same_warehouse(db_session):
    warehouse_id = _active_warehouse_id(db_session)
    provider_id = _provider_id(db_session)
    start = _unique_start(40)

    _insert_appointment(
        db_session,
        provider_id=provider_id,
        warehouse_id=warehouse_id,
        start_time=start,
        duration_minutes=90,
    )

    team_id = _team_id(db_session, warehouse_id)
    with pytest.raises(HTTPException) as exc:
        reserve_slot_fifo_or_raise(
            db_session,
            start + timedelta(minutes=30),
            60,
            team_id,
        )
    assert exc.value.status_code == 409
    assert "equipo" in exc.value.detail.lower()


def test_reserve_slot_exclude_self_allows_reschedule(db_session):
    warehouse_id = _active_warehouse_id(db_session)
    provider_id = _provider_id(db_session)
    start = _unique_start(41)

    appt = _insert_appointment(
        db_session,
        provider_id=provider_id,
        warehouse_id=warehouse_id,
        start_time=start,
        duration_minutes=60,
    )

    reserve_slot_fifo_or_raise(
        db_session,
        start,
        90,
        appt.warehouse_unload_team_id,
        exclude_appointment_id=appt.id,
    )


def test_reserve_slot_non_overlapping_ok(db_session):
    warehouse_id = _active_warehouse_id(db_session)
    provider_id = _provider_id(db_session)
    start = _unique_start(42)

    _insert_appointment(
        db_session,
        provider_id=provider_id,
        warehouse_id=warehouse_id,
        start_time=start,
        duration_minutes=60,
    )

    reserve_slot_fifo_or_raise(
        db_session,
        start + timedelta(hours=3),
        60,
        _team_id(db_session, warehouse_id),
    )


@pytest.mark.parametrize(
    "closed_status",
    [AppointmentStatus.finalizada, AppointmentStatus.no_presentada],
)
def test_unload_team_slot_available_ignores_closed_statuses(db_session, closed_status: AppointmentStatus):
    warehouse_id = _active_warehouse_id(db_session)
    provider_id = _provider_id(db_session)
    team_id = _team_id(db_session, warehouse_id)

    # Buscar un start_time donde el equipo no tenga citas que ya se traslapen.
    # Así el test no depende de datos semilla o de otras pruebas.
    start = None
    for days_ahead in range(220, 251):
        candidate = _unique_start(days_ahead)
        # ventana que usa el servicio para buscar traslapes (~12h hacia atrás)
        window_start = candidate - timedelta(hours=12)
        window_end = candidate + timedelta(minutes=90)
        existing = db_session.execute(
            select(Appointment.id).where(
                Appointment.warehouse_unload_team_id == team_id,
                Appointment.start_time < window_end,
                Appointment.start_time >= window_start,
            )
        ).scalars().all()
        if not existing:
            start = candidate
            break
    assert start is not None, "No se encontró una franja limpia para el test"

    # Cita base (la que intentaremos extender).
    base = _insert_appointment(
        db_session,
        provider_id=provider_id,
        warehouse_id=warehouse_id,
        start_time=start,
        duration_minutes=60,
    )

    # Cita cerrada que cae dentro del rango extendido (start..start+90).
    closed = _insert_appointment(
        db_session,
        provider_id=provider_id,
        warehouse_id=warehouse_id,
        start_time=start + timedelta(minutes=30),
        duration_minutes=60,
    )
    closed.status = closed_status
    db_session.commit()

    from app.services.appointment_service import unload_team_slot_available
    from app.services.appointment_service import _overlapping_appointments_query

    can_extend = unload_team_slot_available(
        db_session,
        team_id,
        start,
        90,
        exclude_appointment_id=base.id,
    )

    # Debug funcional: confirmar si el traslape trae o no a la cita "closed".
    overlaps = list(
        db_session.execute(
            _overlapping_appointments_query(
                start_time=start,
                duration_minutes=90,
                warehouse_unload_team_id=team_id,
                exclude_appointment_id=base.id,
            )
        ).scalars()
    )
    overlap_ids = {a.id for a in overlaps}
    assert closed.status == closed_status
    assert closed.id not in overlap_ids, f"Closed appt incluida en traslape para {closed_status}"
    assert base.id not in overlap_ids, "La cita base debe excluirse del traslape"
    assert len(overlaps) == 0, f"Debe no haber traslapes (encontrados {len(overlaps)})"

    assert can_extend is True
