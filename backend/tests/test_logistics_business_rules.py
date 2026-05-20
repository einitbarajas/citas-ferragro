"""Pruebas unitarias de reglas de negocio de Logística en citas (sin base de datos)."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.appointments import _assert_logistics_business_rules, _staff_modification_actions
from app.api.deps import SecurityPrincipal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import UserRole


def _logistics_principal() -> SecurityPrincipal:
    return SecurityPrincipal(subject="900000001", role_name=UserRole.logistica)


def _admin_principal() -> SecurityPrincipal:
    return SecurityPrincipal(subject="1000000001", role_name=UserRole.admin)


def _appt(status: AppointmentStatus = AppointmentStatus.sin_revision) -> Appointment:
    return Appointment(
        id=1,
        provider_id=1,
        material_description="test",
        start_time=None,
        duration_minutes=60,
        status=status,
    )


def _mock_db_with_actions(actions: list[str]) -> MagicMock:
    db = MagicMock()
    db.execute.return_value.scalars.return_value = iter(actions)
    return db


def test_admin_skips_rules():
    db = _mock_db_with_actions(["extend_duration", "update_status", "update_status"])
    _assert_logistics_business_rules(
        db=db,
        appt=_appt(),
        principal=_admin_principal(),
        target_action="extend_duration",
    )


def test_logistics_closed_appointment_blocks():
    db = _mock_db_with_actions([])
    with pytest.raises(HTTPException) as exc:
        _assert_logistics_business_rules(
            db=db,
            appt=_appt(AppointmentStatus.finalizada),
            principal=_logistics_principal(),
            target_action="update_status",
        )
    assert exc.value.status_code == 409
    assert "cerrada" in exc.value.detail.lower()


def test_logistics_extend_then_update_status_allowed(monkeypatch):
    db = _mock_db_with_actions(["extend_duration"])
    monkeypatch.setattr(
        "app.api.appointments._staff_modification_actions",
        lambda _db, _id: ["extend_duration"],
    )
    _assert_logistics_business_rules(
        db=db,
        appt=_appt(AppointmentStatus.sin_revision),
        principal=_logistics_principal(),
        target_action="update_status",
    )


def test_logistics_extend_twice_blocked(monkeypatch):
    monkeypatch.setattr(
        "app.api.appointments._staff_modification_actions",
        lambda _db, _id: ["extend_duration"],
    )
    with pytest.raises(HTTPException) as exc:
        _assert_logistics_business_rules(
            db=_mock_db_with_actions(["extend_duration"]),
            appt=_appt(AppointmentStatus.sin_revision),
            principal=_logistics_principal(),
            target_action="extend_duration",
        )
    assert exc.value.status_code == 409
    assert "extendida" in exc.value.detail.lower()


def test_logistics_extend_when_revisado_blocked(monkeypatch):
    monkeypatch.setattr(
        "app.api.appointments._staff_modification_actions",
        lambda _db, _id: [],
    )
    with pytest.raises(HTTPException) as exc:
        _assert_logistics_business_rules(
            db=_mock_db_with_actions([]),
            appt=_appt(AppointmentStatus.revisado),
            principal=_logistics_principal(),
            target_action="extend_duration",
        )
    assert exc.value.status_code == 409
    assert "sin revisión" in exc.value.detail.lower()


def test_logistics_revisado_then_confirm_status_allowed(monkeypatch):
    monkeypatch.setattr(
        "app.api.appointments._staff_modification_actions",
        lambda _db, _id: ["update_status"],
    )
    _assert_logistics_business_rules(
        db=_mock_db_with_actions(["update_status"]),
        appt=_appt(AppointmentStatus.revisado),
        principal=_logistics_principal(),
        target_action="update_status",
    )


def test_logistics_full_flow_extend_revisado_confirm(monkeypatch):
    """extend -> revisado -> confirmación: tres pasos permitidos."""
    steps = [
        ([], AppointmentStatus.sin_revision, "extend_duration"),
        (["extend_duration"], AppointmentStatus.sin_revision, "update_status"),
        (["extend_duration", "update_status"], AppointmentStatus.revisado, "update_status"),
    ]
    for actions, status, target in steps:
        monkeypatch.setattr(
            "app.api.appointments._staff_modification_actions",
            lambda _db, _id, a=actions: a,
        )
        _assert_logistics_business_rules(
            db=MagicMock(),
            appt=_appt(status),
            principal=_logistics_principal(),
            target_action=target,
        )


def test_logistics_third_status_change_blocked(monkeypatch):
    monkeypatch.setattr(
        "app.api.appointments._staff_modification_actions",
        lambda _db, _id: ["update_status", "update_status", "update_status"],
    )
    with pytest.raises(HTTPException) as exc:
        _assert_logistics_business_rules(
            db=MagicMock(),
            appt=_appt(AppointmentStatus.revisado),
            principal=_logistics_principal(),
            target_action="update_status",
        )
    assert exc.value.status_code == 409
    assert "estado" in exc.value.detail.lower()


def test_logistics_extend_plus_stale_audit_allows_mark_revisado(monkeypatch):
    """Tras extender, aunque exista un registro antiguo de estado, puede marcar revisado."""
    monkeypatch.setattr(
        "app.api.appointments._staff_modification_actions",
        lambda _db, _id: ["extend_duration", "update_status"],
    )
    _assert_logistics_business_rules(
        db=MagicMock(),
        appt=_appt(AppointmentStatus.sin_revision),
        principal=_logistics_principal(),
        target_action="update_status",
    )


def test_logistics_sin_revision_two_status_changes_then_blocked(monkeypatch):
    monkeypatch.setattr(
        "app.api.appointments._staff_modification_actions",
        lambda _db, _id: ["update_status", "update_status"],
    )
    with pytest.raises(HTTPException) as exc:
        _assert_logistics_business_rules(
            db=MagicMock(),
            appt=_appt(AppointmentStatus.sin_revision),
            principal=_logistics_principal(),
            target_action="update_status",
        )
    assert exc.value.status_code == 409
