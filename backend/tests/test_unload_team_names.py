"""Nombres personalizados de equipos de descarga por bodega."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.appointment import Appointment, AppointmentStatus
from app.models.warehouse import Warehouse
from app.models.warehouse_unload_team import WarehouseUnloadTeam
from app.services.unload_teams import list_active_unload_teams, sync_warehouse_unload_teams, update_warehouse_unload_team_names


def _active_warehouse_id(db_session) -> int:
    wid = db_session.execute(
        select(Warehouse.id).where(Warehouse.active.is_(True)).order_by(Warehouse.id).limit(1)
    ).scalar_one_or_none()
    if wid is None:
        pytest.skip("No hay bodega activa")
    return int(wid)


def test_update_unload_team_names(db_session):
    wid = _active_warehouse_id(db_session)
    teams = list_active_unload_teams(db_session, wid)
    if len(teams) < 1:
        pytest.skip("Sin equipos")

    updated = update_warehouse_unload_team_names(
        db_session,
        wid,
        {teams[0].id: "Muelle Carlos"},
    )
    assert updated[0].name == "Muelle Carlos"
    db_session.rollback()


def test_duplicate_team_names_rejected(db_session):
    wid = _active_warehouse_id(db_session)
    teams = list_active_unload_teams(db_session, wid)
    if len(teams) < 2:
        pytest.skip("Se necesitan al menos 2 equipos en la bodega")

    with pytest.raises(HTTPException) as exc:
        update_warehouse_unload_team_names(
            db_session,
            wid,
            {teams[0].id: "Mismo", teams[1].id: "Mismo"},
        )
    assert exc.value.status_code == 409
    db_session.rollback()


def test_cannot_reduce_teams_with_active_appointment(db_session):
    wid = _active_warehouse_id(db_session)
    teams = list_active_unload_teams(db_session, wid)
    if len(teams) < 2:
        sync_warehouse_unload_teams(db_session, wid, 2)
        teams = list_active_unload_teams(db_session, wid)
    if len(teams) < 2:
        pytest.skip("No se pudieron crear 2 equipos")

    victim = teams[-1]
    provider_id = db_session.execute(
        select(Appointment.provider_id).where(Appointment.provider_id.is_not(None)).limit(1)
    ).scalar_one_or_none()
    if provider_id is None:
        pytest.skip("Sin proveedor para cita de prueba")

    start = datetime.now(timezone.utc) + timedelta(days=45)
    db_session.add(
        Appointment(
            provider_id=provider_id,
            warehouse_id=wid,
            warehouse_unload_team_id=victim.id,
            material_description="Prueba bloqueo muelle",
            start_time=start,
            duration_minutes=60,
            status=AppointmentStatus.revisado,
            provider_team_index=1,
        )
    )
    db_session.flush()

    with pytest.raises(HTTPException) as exc:
        sync_warehouse_unload_teams(db_session, wid, len(teams) - 1)
    assert exc.value.status_code == 409
    assert victim.name in str(exc.value.detail) or "muelle" in str(exc.value.detail).lower()
    db_session.rollback()


def test_list_active_preserves_configured_team_count(db_session):
    wid = _active_warehouse_id(db_session)
    warehouse = db_session.get(Warehouse, wid)
    sync_warehouse_unload_teams(db_session, wid, 3)
    db_session.commit()
    db_session.refresh(warehouse)
    assert warehouse.unload_teams == 3

    list_active_unload_teams(db_session, wid, commit=True)
    db_session.refresh(warehouse)
    assert warehouse.unload_teams == 3
    active = list_active_unload_teams(db_session, wid)
    assert len(active) == 3
    db_session.rollback()


def test_rename_active_frees_name_from_inactive(db_session):
    wid = _active_warehouse_id(db_session)
    sync_warehouse_unload_teams(db_session, wid, 2)
    all_rows = list(
        db_session.execute(
            select(WarehouseUnloadTeam)
            .where(WarehouseUnloadTeam.warehouse_id == wid)
            .order_by(WarehouseUnloadTeam.sort_order, WarehouseUnloadTeam.id)
        )
        .scalars()
        .all()
    )
    if len(all_rows) < 2:
        pytest.skip("Sin filas de equipo")

    inactive = all_rows[1]
    inactive.active = False
    inactive.name = "Carlos"
    db_session.flush()
    active = all_rows[0]

    updated = update_warehouse_unload_team_names(db_session, wid, {active.id: "Carlos"})
    assert updated[0].name == "Carlos"
    db_session.refresh(inactive)
    assert "inactivo" in inactive.name.lower() or "reservado" in inactive.name.lower()
    db_session.rollback()
