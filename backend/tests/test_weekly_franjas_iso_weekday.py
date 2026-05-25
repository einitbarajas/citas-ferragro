"""Franjas semanales respetan día ISO (lun–vie vs sáb–dom)."""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import delete, select

from app.models.appointment_window import AppointmentWindow
from app.models.warehouse import Warehouse
from app.services.appointment_windows import (
    day_has_team_schedule,
    list_team_open_days_in_month,
    list_weekly_iso_weekdays,
    list_windows_ordered,
    replace_windows,
)
from app.services.unload_teams import list_active_unload_teams


def _active_warehouse_team(db_session):
    wid = db_session.execute(
        select(Warehouse.id).where(Warehouse.active.is_(True)).order_by(Warehouse.id).limit(1)
    ).scalar_one_or_none()
    if wid is None:
        pytest.skip("Sin bodega activa")
    teams = list_active_unload_teams(db_session, int(wid))
    if not teams:
        pytest.skip("Sin equipos de descarga")
    return int(wid), teams[0].id


def test_weekly_franjas_only_on_selected_iso_weekdays(db_session):
    wid, team_id = _active_warehouse_team(db_session)
    db_session.execute(
        delete(AppointmentWindow).where(
            AppointmentWindow.warehouse_id == wid,
            AppointmentWindow.warehouse_unload_team_id == team_id,
        )
    )
    db_session.commit()

    replace_windows(
        db_session,
        wid,
        [(time(8, 0), time(9, 0))],
        team_id,
        iso_weekdays=[1, 2, 3, 4, 5],
    )

    assert list_weekly_iso_weekdays(db_session, wid, team_id) == [1, 2, 3, 4, 5]
    assert list_windows_ordered(db_session, wid, team_id, for_day=date(2026, 5, 25))  # lun
    assert not list_windows_ordered(db_session, wid, team_id, for_day=date(2026, 5, 31))  # dom

    assert day_has_team_schedule(db_session, date(2026, 5, 27), wid, team_id) is True
    assert day_has_team_schedule(db_session, date(2026, 5, 31), wid, team_id) is False

    open_may = list_team_open_days_in_month(db_session, 2026, 5, wid, team_id)
    assert "2026-05-31" not in open_may
    assert "2026-05-27" in open_may

    db_session.rollback()
