"""Pruebas unitarias del servicio de citas (sin base de datos)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.models.appointment import Appointment, AppointmentStatus
from app.services import appointment_service as svc


def test_enforce_minimum_notice_rejects_too_soon():
    soon = datetime.now(timezone.utc) + timedelta(hours=12)
    with pytest.raises(HTTPException) as exc:
        svc.enforce_minimum_notice(soon, minimum_hours=24)
    assert exc.value.status_code == 400
    assert "24" in exc.value.detail


def test_enforce_minimum_notice_accepts_far_enough():
    ok = datetime.now(timezone.utc) + timedelta(hours=48)
    svc.enforce_minimum_notice(ok, minimum_hours=24)


def test_can_extend_without_overlap_no_next_appointment():
    db = MagicMock()
    warehouse = MagicMock()
    warehouse.unload_teams = 2
    db.get.return_value = warehouse
    db.execute.return_value.scalars.return_value = iter([])
    appt = Appointment(
        id=1,
        provider_id=1,
        warehouse_id=1,
        material_description="x",
        start_time=datetime.now(timezone.utc),
        duration_minutes=60,
        status=AppointmentStatus.sin_revision,
    )
    assert svc.can_extend_without_overlap(db, appt, 30) is True


def test_can_extend_without_overlap_blocked_by_capacity():
    db = MagicMock()
    warehouse = MagicMock()
    warehouse.unload_teams = 1
    db.get.return_value = warehouse
    start = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    appt = Appointment(
        id=1,
        provider_id=1,
        warehouse_id=1,
        material_description="x",
        start_time=start,
        duration_minutes=60,
        status=AppointmentStatus.sin_revision,
    )
    other = Appointment(
        id=2,
        provider_id=2,
        warehouse_id=1,
        material_description="y",
        start_time=start + timedelta(minutes=30),
        duration_minutes=60,
        status=AppointmentStatus.sin_revision,
    )
    db.execute.return_value.scalars.return_value = iter([other])
    assert svc.can_extend_without_overlap(db, appt, 30) is False


def test_finalize_elapsed_throttled(monkeypatch):
    monkeypatch.setattr(svc, "_finalize_last_run_monotonic", 1000.0)
    monkeypatch.setattr("app.services.appointment_service.time.monotonic", lambda: 1000.5)
    db = MagicMock()
    assert svc.finalize_elapsed_appointments(db) == 0
    db.execute.assert_not_called()


def test_provider_capacity_allows_parallel_when_teams_gt_one():
    db = MagicMock()
    provider = MagicMock()
    provider.unload_teams = 2
    db.get.return_value = provider
    start = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    other = Appointment(
        id=2,
        provider_id=99,
        warehouse_id=2,
        material_description="y",
        start_time=start,
        duration_minutes=60,
        status=AppointmentStatus.sin_revision,
    )
    db.execute.return_value.scalars.return_value = iter([other])
    assert svc.provider_schedule_conflicts(db, 99, start, 60) is False


def test_provider_schedule_conflicts_detects_overlap():
    db = MagicMock()
    provider = MagicMock()
    provider.unload_teams = 1
    db.get.return_value = provider
    start = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    other = Appointment(
        id=2,
        provider_id=99,
        warehouse_id=2,
        material_description="y",
        start_time=start + timedelta(minutes=30),
        duration_minutes=60,
        status=AppointmentStatus.sin_revision,
    )
    db.execute.return_value.scalars.return_value = iter([other])
    assert svc.provider_schedule_conflicts(db, 99, start, 60) is True


def test_provider_schedule_conflicts_ignores_non_overlapping():
    db = MagicMock()
    provider = MagicMock()
    provider.unload_teams = 1
    db.get.return_value = provider
    start = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    other = Appointment(
        id=2,
        provider_id=99,
        warehouse_id=2,
        material_description="y",
        start_time=start + timedelta(hours=3),
        duration_minutes=60,
        status=AppointmentStatus.sin_revision,
    )
    db.execute.return_value.scalars.return_value = iter([other])
    assert svc.provider_schedule_conflicts(db, 99, start, 60) is False


def test_slot_conflict_check_returns_true_when_team_busy(monkeypatch):
    monkeypatch.setattr(svc, "unload_team_slot_available", lambda *_a, **_k: False)
    monkeypatch.setattr(svc, "provider_capacity_available", lambda *_a, **_k: True)
    assert svc.slot_conflict_check(MagicMock(), datetime.now(timezone.utc), 60, 1) is True


def test_slot_conflict_check_returns_false_when_free(monkeypatch):
    monkeypatch.setattr(svc, "unload_team_slot_available", lambda *_a, **_k: True)
    monkeypatch.setattr(svc, "provider_capacity_available", lambda *_a, **_k: True)
    assert svc.slot_conflict_check(MagicMock(), datetime.now(timezone.utc), 60, 1) is False
