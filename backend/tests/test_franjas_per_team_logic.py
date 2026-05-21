"""Franjas por muelle: bloqueo de edición solo por citas del mismo equipo."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.api.crud import _appointments_count_on_local_day
from app.models.appointment import Appointment, AppointmentStatus
from app.models.warehouse import Warehouse
from app.models.warehouse_unload_team import WarehouseUnloadTeam
from app.services.unload_teams import list_active_unload_teams


def _warehouse_and_two_teams(db_session):
    wid = db_session.execute(
        select(Warehouse.id).where(Warehouse.active.is_(True)).order_by(Warehouse.id).limit(1)
    ).scalar_one_or_none()
    if wid is None:
        pytest.skip("Sin bodega activa")
    teams = list_active_unload_teams(db_session, int(wid))
    if len(teams) < 2:
        pytest.skip("Se necesitan al menos 2 equipos en la bodega")
    return int(wid), teams[0], teams[1]


def test_appointments_count_is_per_unload_team(db_session):
    wid, team_a, team_b = _warehouse_and_two_teams(db_session)
    target_day = date(2030, 6, 15)
    start = datetime(2030, 6, 15, 14, 0, tzinfo=timezone.utc)
    provider_id = db_session.execute(select(Appointment.provider_id).limit(1)).scalar_one_or_none()
    if provider_id is None:
        pytest.skip("Sin proveedor")

    db_session.add(
        Appointment(
            provider_id=provider_id,
            warehouse_id=wid,
            warehouse_unload_team_id=team_a.id,
            material_description="Prueba franjas por equipo",
            start_time=start,
            duration_minutes=60,
            status=AppointmentStatus.revisado,
            provider_team_index=1,
        )
    )
    db_session.flush()

    assert _appointments_count_on_local_day(db_session, target_day, wid, team_a.id) == 1
    assert _appointments_count_on_local_day(db_session, target_day, wid, team_b.id) == 0
    assert _appointments_count_on_local_day(db_session, target_day, wid) == 1
    db_session.rollback()
