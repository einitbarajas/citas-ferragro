"""Analítica: filtro por día usa zona horaria de negocio (no fecha UTC)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import func, select, text

from app.api.crud import analytics_summary
from app.core.config import settings
from app.models.appointment import Appointment
from app.services.range_bounds import appointment_local_date_sql


def test_appointment_local_date_sql_matches_bogota_calendar(db_session):
    """Una marca 03:00 UTC debe leerse como el día anterior en Bogotá."""
    tz_name = settings.business_timezone
    local_day = db_session.execute(
        text(
            "SELECT (timezone(:tz, timestamptz '2026-05-27 03:00:00+00'))::date"
        ),
        {"tz": tz_name},
    ).scalar_one()
    assert local_day == date(2026, 5, 26)


def test_analytics_today_with_day_param_returns_totals(db_session):
    """Si hay citas en un día local, totales_por_estado no debe quedar vacío por desfase UTC."""
    tz_name = settings.business_timezone
    local_date_expr = appointment_local_date_sql(Appointment.start_time, tz_name)
    target_day = date(2026, 5, 27)
    count = (
        db_session.execute(
            select(func.count()).where(local_date_expr == target_day)
        ).scalar_one()
        or 0
    )
    if count == 0:
        pytest.skip("No hay citas el 2026-05-27 (hora local) en la BD de pruebas")

    response = analytics_summary(
        range_mode="today",
        period=None,
        day=target_day,
        month=None,
        year=None,
        warehouse_id=None,
        db=db_session,
    )
    payload = response.get("data") or {}
    assert payload.get("total_citas") == int(count)
    assert sum((payload.get("totales_por_estado") or {}).values()) == int(count)
