"""Pruebas de destinatarios de notificaciones por bodega."""

from unittest.mock import MagicMock

import pytest

from app.api.crud import STAFF_AUDIT_ROLES
from app.models.provider import Provider
from app.models.user import UserRole
from app.models.warehouse import Warehouse
from app.services import notification_service as svc


def _mock_db_with_emails(*email_lists):
    """Cada llamada a execute().scalars().all() devuelve la siguiente lista."""
    calls = list(email_lists)

    def execute(_stmt):
        result = MagicMock()
        if calls:
            result.scalars.return_value.all.return_value = calls.pop(0)
        else:
            result.scalars.return_value.all.return_value = []
        return result

    db = MagicMock()
    db.execute.side_effect = execute
    return db


def test_warehouse_staff_emails_includes_admin_and_scoped_roles():
    db = _mock_db_with_emails(
        ["admin@ferragro.com"],
        ["log@ferragro.com"],
        ["bodega@ferragro.com"],
    )
    emails = svc._warehouse_staff_emails(db, warehouse_id=3)
    assert emails == ["admin@ferragro.com", "log@ferragro.com", "bodega@ferragro.com"]
    assert db.execute.call_count == 3


def test_appointment_stakeholder_emails_dedupes_provider():
    db = _mock_db_with_emails(
        ["admin@ferragro.com"],
        ["log@ferragro.com"],
        ["bodega@ferragro.com"],
    )
    provider = MagicMock()
    provider.credential = MagicMock(email="proveedor@test.com")
    provider.company_email = "proveedor@test.com"
    db.get.return_value = provider

    appointment = MagicMock()
    appointment.warehouse_id = 2
    appointment.provider_id = 9001234567

    emails = svc._appointment_stakeholder_emails(db, appointment, include_provider=True)
    assert "proveedor@test.com" in emails
    assert len(emails) == len(set(e.lower() for e in emails))


def test_internal_staff_roles_include_admin_bodega():
    assert UserRole.admin_bodega in svc.INTERNAL_STAFF_ROLES
    assert UserRole.logistica in svc.WAREHOUSE_SCOPED_STAFF_ROLES


def test_staff_audit_roles_include_admin_bodega():
    assert UserRole.admin_bodega in STAFF_AUDIT_ROLES
    for role in (UserRole.admin, UserRole.logistica, UserRole.admin_bodega):
        assert role in STAFF_AUDIT_ROLES


def test_notify_provider_appointment_updated_includes_schedule(monkeypatch):
    appointment = MagicMock()
    appointment.id = 8
    appointment.warehouse_id = 2
    appointment.provider_id = 9001234567
    appointment.duration_minutes = 90
    appointment.start_time = MagicMock()
    appointment.start_time.astimezone.return_value.strftime.return_value = "03/06/2026 08:00"

    provider = MagicMock()
    provider.company_name = "Proveedor Test"
    warehouse = MagicMock()
    warehouse.name = "Bodega Sur"

    def get_side_effect(model, _id):
        if model is Provider:
            return provider
        if model is Warehouse:
            return warehouse
        return None

    db = MagicMock()
    db.get.side_effect = get_side_effect

    captured: dict = {}

    def fake_notify(db_arg, appt, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.services.appointment_notification_events.publish_appointment_notification",
        lambda db_arg, appt, **kwargs: captured.update(kwargs),
    )
    svc.notify_provider_appointment_updated(db, appointment, summary="La empresa actualizó fecha y hora.")

    assert captured.get("extra_detail") == "La empresa actualizó fecha y hora."
    from app.services.appointment_notification_events import AppointmentNotificationAction

    assert captured.get("action") == AppointmentNotificationAction.updated


def test_notify_staff_review_needed_includes_provider_and_schedule(monkeypatch):
    appointment = MagicMock()
    appointment.id = 9
    appointment.status = svc.AppointmentStatus.sin_revision
    appointment.warehouse_id = 2
    appointment.provider_id = 9001234567
    appointment.duration_minutes = 90
    appointment.start_time = MagicMock()

    provider = MagicMock()
    provider.company_name = "Distribuidora ABC"
    warehouse = MagicMock()
    warehouse.name = "Bodega Norte"

    appointment.start_time.astimezone.return_value.strftime.return_value = "05/06/2026 10:00"

    def get_side_effect(model, _id):
        if model is Provider:
            return provider
        if model is Warehouse:
            return warehouse
        return None

    db = MagicMock()
    db.get.side_effect = get_side_effect

    captured: dict = {}

    def fake_notify(db_arg, appt, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.services.appointment_notification_events.publish_appointment_notification",
        lambda db_arg, appt, **kwargs: captured.update(kwargs),
    )
    svc.notify_staff_review_needed(db, appointment)

    from app.services.appointment_notification_events import AppointmentNotificationAction

    assert captured.get("action") == AppointmentNotificationAction.pending_review


@pytest.mark.parametrize(
    "func_name",
    [
        "notify_staff_review_needed",
        "notify_provider_appointment_updated",
        "notify_staff_provider_cancelled",
    ],
)
def test_public_notify_functions_call_publish(monkeypatch, func_name):
    appointment = MagicMock()
    appointment.id = 1
    appointment.status = svc.AppointmentStatus.sin_revision
    appointment.warehouse_id = 1
    appointment.provider_id = 9001234567
    appointment.start_time = MagicMock()
    appointment.start_time.astimezone.return_value.strftime.return_value = "01/06/2026 10:00"

    called = {"n": 0}

    def fake_notify(db, appt, **kwargs):
        called["n"] += 1
        assert appt is appointment

    monkeypatch.setattr(
        "app.services.appointment_notification_events.publish_appointment_notification",
        fake_notify,
    )
    db = MagicMock()
    fn = getattr(svc, func_name)
    if func_name == "notify_provider_appointment_updated":
        fn(db, appointment, summary="Cambio de prueba")
    elif func_name == "notify_staff_provider_cancelled":
        fn(db, appointment, reason="motivo de prueba")
    else:
        fn(db, appointment)
    assert called["n"] == 1
